using Remaster.Core;
using System.Text.Json;

static class Program
{
 private static int passed;
 private static void Check(bool condition, string name)
 {
 if (!condition) throw new Exception("FAILED: " + name);
 passed++;
 }
 private static void Throws<T>(Action action, string name) where T : Exception
 {
 try { action(); }
 catch (T) { passed++; return; }
 throw new Exception("Expected " + typeof(T).Name + ": " + name);
 }
 private static Simulation Setup()
 {
 var sim = new Simulation(4, 4, 123, new[] { new Cell(1, 1) });
 sim.AddActor("b", new Cell(3, 3));
 sim.AddActor("a", new Cell(0, 0));
 return sim;
 }
 private static void Main()
 {
 var detour = new Simulation(3, 3, 1, new[] { new Cell(1, 0) });
 detour.AddActor("hero", new Cell(0, 0));
 detour.Step(new MoveCommand("hero", new Cell(2, 0)));
 Check(detour.GetPosition("hero") == new Cell(0, 1), "BFS detour first step");
 Check(detour.RemainingPath("hero").Count == 3, "one cell per tick");
 for (int i = 0; i < 3; i++) detour.Step();
 Check(detour.GetPosition("hero") == new Cell(2, 0) && detour.Tick == 4, "detour completion");
 Check(detour.RemainingPath("hero").Count == 0, "completed path empty");

 var cut = new Simulation(3, 3, 42, new[] { new Cell(1, 0), new Cell(1, 1), new Cell(1, 2) });
 cut.AddActor("a", new Cell(0, 1));
 var frozen = cut.Save();
 Throws<InvalidOperationException>(() => cut.Step(new MoveCommand("a", new Cell(2, 1))), "unreachable");
 Throws<ArgumentException>(() => cut.Step(new MoveCommand("a", new Cell(1, 1))), "blocked goal");
 Throws<ArgumentException>(() => cut.Step(new MoveCommand("missing", new Cell(0, 0))), "unknown actor");
 Check(cut.Save() == frozen, "invalid commands leave state unchanged");

 var ordered = Setup();
 ordered.Step(new MoveCommand("a", new Cell(3, 0)), new MoveCommand("a", new Cell(0, 3)));
 Check(ordered.GetPosition("a") == new Cell(0, 1), "last command wins");
 var before = ordered.Save();
 Throws<ArgumentException>(() => ordered.Step(new MoveCommand("a", new Cell(0, 2)),
 new MoveCommand("missing", new Cell(0, 0))), "atomic command batch");
 Check(ordered.Save() == before, "batch rollback by prevalidation");

 var first = new Simulation(3, 3, 7, new[] { new Cell(2, 2), new Cell(2, 1) });
 var second = new Simulation(3, 3, 7, new[] { new Cell(2, 1), new Cell(2, 2) });
 first.AddActor("z", new Cell(1, 0)); first.AddActor("a", new Cell(0, 0));
 second.AddActor("a", new Cell(0, 0)); second.AddActor("z", new Cell(1, 0));
 Check(first.Save() == second.Save() && first.SnapshotDigest() == second.SnapshotDigest(),
 "canonical ordering independent of insertion");
 Check(new Simulation(1, 1, 1).NextRandom() == 270369u, "xorshift32 vector");

 var live = Setup();
 var replay = Setup();
 live.Step(new MoveCommand("a", new Cell(3, 0)), new MoveCommand("b", new Cell(0, 3)));
 replay.Step(new MoveCommand("a", new Cell(3, 0)), new MoveCommand("b", new Cell(0, 3)));
 Check(live.NextRandom() == replay.NextRandom(), "independent seeded RNG");
 Check(live.SnapshotDigest() == replay.SnapshotDigest(), "independent trace start");
 var saved = live.Save();
 var loaded = Simulation.Load(saved);
 Check(loaded.Save() == saved && loaded.SnapshotDigest() == live.SnapshotDigest(), "V1 roundtrip");
 for (int i = 0; i < 5; i++)
 {
 live.Step(); replay.Step(); loaded.Step();
 uint liveRandom = live.NextRandom();
 uint loadedRandom = loaded.NextRandom();
 uint replayRandom = replay.NextRandom();
 Check(liveRandom == loadedRandom && replayRandom == liveRandom, "RNG continuation " + i);
 Check(live.SnapshotDigest() == loaded.SnapshotDigest() &&
 replay.SnapshotDigest() == live.SnapshotDigest(), "trace continuation " + i);
 }

 var basic = Setup().Save();
 Throws<InvalidDataException>(() => Simulation.Load(basic.Replace("\"version\":1", "\"version\":2")), "version");
 Throws<InvalidDataException>(() => Simulation.Load(basic.Replace("\"tick\":0", "\"tick\":-1")), "negative tick");
 Throws<ArgumentOutOfRangeException>(() => Simulation.Load(basic.Replace("\"rng\":123", "\"rng\":0")), "zero RNG");
 Throws<JsonException>(() => Simulation.Load(basic.Replace("\"version\":1", "\"version\":1,\"version\":1")), "duplicate JSON key");
 Throws<JsonException>(() => Simulation.Load(basic.Replace("\"tick\":0,", "")), "missing required field");
 Throws<JsonException>(() => Simulation.Load(basic.Replace("\"version\":1,", "\"version\":1,\"unknown\":1,")), "unknown field");
 Throws<ArgumentException>(() => Simulation.Load(basic.Replace("\"actors\":[",
 "\"actors\":[{\"id\":\"a\",\"position\":{\"x\":0,\"y\":0},\"path\":[]},")), "duplicate actor ID");
 Throws<InvalidDataException>(() => Simulation.Load(basic.Replace("\"path\":[]",
 "\"path\":[{\"x\":3,\"y\":0}]")), "invalid saved path");
 var wall = new Simulation(2, 2, 1, new[] { new Cell(1, 1) }).Save();
 Throws<ArgumentException>(() => Simulation.Load(wall.Replace("\"blocked\":[",
 "\"blocked\":[{\"x\":1,\"y\":1},")), "duplicate blocked cell");
 Throws<ArgumentException>(() => Setup().AddActor("a", new Cell(0, 0)), "duplicate API actor");
 Throws<ArgumentOutOfRangeException>(() => new Simulation(5000, 1, 1), "grid size limit");
 Console.WriteLine("PASS: " + passed + " assertions");
 }
}
