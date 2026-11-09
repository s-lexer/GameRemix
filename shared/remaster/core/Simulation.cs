using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Remaster.Core;

public readonly record struct Cell([property: JsonRequired] int X, [property: JsonRequired] int Y);
public sealed record MoveCommand(string ActorId, Cell Destination);

public sealed class Simulation
{
 public const int Version = 1;
 private static readonly Cell[] Neighbors =
 {
 new(0, -1), new(1, 0), new(0, 1), new(-1, 0)
 };
 private static readonly JsonSerializerOptions Options = new()
 {
 PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
 UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
 };
 private readonly HashSet<Cell> walls = new();
 private readonly SortedDictionary<string, Actor> actors = new(StringComparer.Ordinal);
 private uint rng;

 private sealed class Actor
 {
 public Cell Position;
 public List<Cell> Path = new();
 public Actor(Cell position) => Position = position;
 }
 private sealed class SavedActor
 {
 public SavedActor() { }
 public required string Id { get; init; }
 public required Cell Position { get; init; }
 public required Cell[] Path { get; init; }
 }
 private sealed class SavedState
 {
 public SavedState() { }
 public required int Version { get; init; }
 public required int Width { get; init; }
 public required int Height { get; init; }
 public required long Tick { get; init; }
 public required uint Rng { get; init; }
 public required Cell[] Blocked { get; init; }
 public required SavedActor[] Actors { get; init; }
 }

 public int Width { get; }
 public int Height { get; }
 public long Tick { get; private set; }
 public uint RngState => rng;

 public Simulation(int width, int height, uint seed, IEnumerable<Cell>? blocked = null)
 {
 if (width < 1 || height < 1 || (long)width * height > 4096)
 throw new ArgumentOutOfRangeException(nameof(width), "Grid must contain 1..4096 cells.");
 if (seed == 0) throw new ArgumentOutOfRangeException(nameof(seed), "Xorshift32 requires a nonzero state.");
 Width = width;
 Height = height;
 rng = seed;
 foreach (var cell in blocked ?? Array.Empty<Cell>())
 {
 RequireCell(cell);
 if (!walls.Add(cell)) throw new ArgumentException("Duplicate blocked cell.", nameof(blocked));
 }
 }

 private void RequireCell(Cell cell)
 {
 if (cell.X < 0 || cell.Y < 0 || cell.X >= Width || cell.Y >= Height)
 throw new ArgumentOutOfRangeException(nameof(cell), "Cell outside grid.");
 }
 private void RequireOpen(Cell cell)
 {
 RequireCell(cell);
 if (walls.Contains(cell)) throw new ArgumentException("Cell is blocked.", nameof(cell));
 }
 private static void RequireId(string? id)
 {
 if (string.IsNullOrEmpty(id) || id.Length > 64 || id.Any(c =>
 !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
 (c >= '0' && c <= '9') || c == '_' || c == '-')))
 throw new ArgumentException("Actor ID must be 1..64 ASCII letters, digits, _ or -.", nameof(id));
 }
 public void AddActor(string id, Cell position)
 {
 RequireId(id);
 RequireOpen(position);
 if (actors.ContainsKey(id)) throw new ArgumentException("Duplicate actor ID.", nameof(id));
 actors.Add(id, new Actor(position));
 }
 public Cell GetPosition(string id) => actors[id].Position;
 public IReadOnlyList<Cell> RemainingPath(string id) => actors[id].Path.ToArray();

 // Caller command order is significant: last valid command for an actor wins.
 // All commands are validated before any position, path or tick changes.
 public void Step(params MoveCommand[] commands)
 {
 ArgumentNullException.ThrowIfNull(commands);
 if (Tick == long.MaxValue) throw new InvalidOperationException("Tick counter exhausted.");
 var updates = new Dictionary<string, List<Cell>>(StringComparer.Ordinal);
 foreach (var command in commands)
 {
 if (command is null) throw new ArgumentException("Null command.", nameof(commands));
 RequireId(command.ActorId);
 if (!actors.TryGetValue(command.ActorId, out var actor))
 throw new ArgumentException("Unknown actor ID.", nameof(commands));
 RequireOpen(command.Destination);
 updates[command.ActorId] = Route(actor.Position, command.Destination);
 }
 foreach (var update in updates) actors[update.Key].Path = update.Value;
 foreach (var actor in actors.Values)
 {
 if (actor.Path.Count == 0) continue;
 actor.Position = actor.Path[0];
 actor.Path.RemoveAt(0);
 }
 Tick++;
 }

 // BFS uses Up, Right, Down, Left; actors do not dynamically block cells.
 private List<Cell> Route(Cell start, Cell goal)
 {
 var queue = new Queue<Cell>();
 var previous = new Dictionary<Cell, Cell> { [start] = start };
 queue.Enqueue(start);
 while (queue.Count > 0 && !previous.ContainsKey(goal))
 {
 var current = queue.Dequeue();
 foreach (var delta in Neighbors)
 {
 var next = new Cell(current.X + delta.X, current.Y + delta.Y);
 if (next.X < 0 || next.Y < 0 || next.X >= Width || next.Y >= Height ||
 walls.Contains(next) || previous.ContainsKey(next)) continue;
 previous.Add(next, current);
 queue.Enqueue(next);
 }
 }
 if (!previous.ContainsKey(goal)) throw new InvalidOperationException("Destination unreachable.");
 var path = new List<Cell>();
 for (var cell = goal; cell != start; cell = previous[cell]) path.Add(cell);
 path.Reverse();
 return path;
 }

 // Xorshift32: unsigned 32-bit state, shifts 13/17/5, wrapping arithmetic.
 // RNG is explicit and never consumed implicitly by movement.
 public uint NextRandom()
 {
 uint x = rng;
 x ^= x << 13;
 x ^= x >> 17;
 x ^= x << 5;
 rng = x;
 return x;
 }

 // Canonical V1 JSON: sorted walls (Y,X), ordinal actor IDs, ordered paths.
 public string Save() => JsonSerializer.Serialize(new SavedState
 {
 Version = Version, Width = Width, Height = Height, Tick = Tick, Rng = rng,
 Blocked = walls.OrderBy(c => c.Y).ThenBy(c => c.X).ToArray(),
 Actors = actors.Select(a => new SavedActor
 {
 Id = a.Key, Position = a.Value.Position, Path = a.Value.Path.ToArray()
 }).ToArray()
 }, Options);

 public string SnapshotDigest() => Convert.ToHexString(
 SHA256.HashData(Encoding.UTF8.GetBytes(Save()))).ToLowerInvariant();

 public static Simulation Load(string json)
 {
 ArgumentNullException.ThrowIfNull(json);
 using var document = JsonDocument.Parse(json);
 RejectDuplicateProperties(document.RootElement);
 var state = JsonSerializer.Deserialize<SavedState>(json, Options)
 ?? throw new JsonException("Null state.");
 if (state.Version != Version) throw new InvalidDataException("Unsupported state version.");
 if (state.Tick < 0) throw new InvalidDataException("Negative tick.");
 if (state.Blocked is null || state.Actors is null)
 throw new InvalidDataException("Null state collection.");
 var sim = new Simulation(state.Width, state.Height, state.Rng, state.Blocked)
 {
 Tick = state.Tick
 };
 foreach (var saved in state.Actors)
 {
 if (saved is null || saved.Path is null) throw new InvalidDataException("Null actor or path.");
 sim.AddActor(saved.Id, saved.Position);
 var seen = new HashSet<Cell> { saved.Position };
 var previous = saved.Position;
 foreach (var next in saved.Path)
 {
 sim.RequireOpen(next);
 if (Math.Abs(next.X - previous.X) + Math.Abs(next.Y - previous.Y) != 1 ||
 !seen.Add(next))
 throw new InvalidDataException("Noncontiguous or cyclic actor path.");
 sim.actors[saved.Id].Path.Add(next);
 previous = next;
 }
 }
 return sim;
 }

 private static void RejectDuplicateProperties(JsonElement element)
 {
 if (element.ValueKind == JsonValueKind.Object)
 {
 var names = new HashSet<string>(StringComparer.Ordinal);
 foreach (var property in element.EnumerateObject())
 {
 if (!names.Add(property.Name)) throw new JsonException("Duplicate JSON property.");
 RejectDuplicateProperties(property.Value);
 }
 }
 else if (element.ValueKind == JsonValueKind.Array)
 foreach (var child in element.EnumerateArray()) RejectDuplicateProperties(child);
 }
}
