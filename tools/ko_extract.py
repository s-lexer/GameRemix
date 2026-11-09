# -*- coding: utf-8 -*-
"""Collects every ENGLISH interface string of GameRemix (key of src/ko.txt): (ru, en) argument pairs of calls in src/*.cs, the English columns of
games/divine-divinity/gfx/gfx.txt and the English help texts. Writes scratch/ko/en_strings.json: [{"en":..., "ru":..., "src":...}], prefix keys marked "prefix".
Run: python tools/ko_extract.py"""
import re, glob, json, os, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CYR = re.compile('[Ѐ-ӿ]')
ESC = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '\\': '\\', '"': '"', "'": "'", 'a': '\a', 'b': '\b', 'f': '\f', 'v': '\v'}

def unesc(body, verbatim=False):
    if verbatim: return body.replace('""', '"')
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == '\\' and i + 1 < len(body):
            n = body[i + 1]
            if n == 'u' and i + 5 < len(body) + 0: out.append(chr(int(body[i + 2:i + 6], 16))); i += 6; continue
            if n == 'x':
                m = re.match(r'[0-9a-fA-F]{1,4}', body[i + 2:]); out.append(chr(int(m.group(0), 16))); i += 2 + len(m.group(0)); continue
            out.append(ESC.get(n, n)); i += 2; continue
        out.append(c); i += 1
    return ''.join(out)

def strip_comments(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '"' or (c == '@' and s[i + 1:i + 2] == '"') or (c == '$' and s[i + 1:i + 2] == '"'):
            j = i; verb = c == '@'
            if c in '@$': j += 1
            j += 1
            while j < n:
                if verb:
                    if s[j] == '"':
                        if s[j + 1:j + 2] == '"': j += 2; continue
                        break
                else:
                    if s[j] == '\\': j += 2; continue
                    if s[j] == '"': break
                j += 1
            out.append(s[i:j + 1]); i = j + 1; continue
        if c == "'":
            j = i + 1
            while j < n and s[j] != "'":
                j += 2 if s[j] == '\\' else 1
            out.append(s[i:j + 1]); i = j + 1; continue
        if s.startswith('//', i):
            while i < n and s[i] != '\n': i += 1
            continue
        if s.startswith('/*', i):
            j = s.find('*/', i + 2); i = n if j < 0 else j + 2; continue
        out.append(c); i += 1
    return ''.join(out)

LIT = re.compile(r'(@?)"((?:[^"\\\n]|\\.)*)"')
def split_args(s, i):   # s[i] == '(' ; returns (list of arg source strings, index after ')')
    depth, args, cur, j, n = 0, [], [], i, len(s)
    while j < n:
        c = s[j]
        if c == '"' or (c == '@' and s[j + 1:j + 2] == '"') or c == '$' and s[j + 1:j + 2] == '"':
            k = j; verb = c == '@'
            if c in '@$': k += 1
            k += 1
            while k < n:
                if verb:
                    if s[k] == '"':
                        if s[k + 1:k + 2] == '"': k += 2; continue
                        break
                else:
                    if s[k] == '\\': k += 2; continue
                    if s[k] == '"': break
                k += 1
            cur.append(s[j:k + 1]); j = k + 1; continue
        if c == "'":
            k = j + 1
            while k < n and s[k] != "'": k += 2 if s[k] == '\\' else 1
            cur.append(s[j:k + 1]); j = k + 1; continue
        if c in '([{':
            depth += 1
            if depth > 1: cur.append(c)
        elif c in ')]}':
            depth -= 1
            if depth == 0: args.append(''.join(cur)); return args, j + 1
            cur.append(c)
        elif c == ',' and depth == 1: args.append(''.join(cur)); cur = []
        else: cur.append(c)
        j += 1
    return args, n

def lead_lit(arg):   # (text, pure) : the leading string literal of an argument; pure = the argument is only that literal (adjacent literals joined with +)
    a = arg.strip(); m = LIT.match(a)
    if not m or a.startswith('$'): return None, False
    text = unesc(m.group(2), bool(m.group(1))); rest = a[m.end():].strip()
    while rest.startswith('+'):
        m2 = LIT.match(rest[1:].strip())
        if not m2: return text, False
        text += unesc(m2.group(2), bool(m2.group(1))); rest = rest[1:].strip()[m2.end():].strip()
    return text, rest == ''

def from_cs():
    found = {}; skipped = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'src', '*.cs'))):
        s = strip_comments(open(p, encoding='utf-8').read()); name = os.path.basename(p)
        for m in re.finditer(r'[A-Za-z_][A-Za-z0-9_.]*\s*\(', s):
            i = m.end() - 1; args, _ = split_args(s, i)
            for k in range(len(args) - 1):
                ru, rp = lead_lit(args[k]); en, ep = lead_lit(args[k + 1])
                if ru is None or en is None or not CYR.search(ru) or CYR.search(en) or not re.search('[A-Za-z]', en): continue
                if ep: found.setdefault(en, (ru, name))
                elif en.endswith((': ', ' — ', '… ')) and len(en) > 3: found.setdefault(en, (ru, name + ' prefix'))
                else: skipped.append((name, en[:70]))
    return found, skipped

def from_gfx():
    out = {}
    for ln in open(os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'gfx.txt'), encoding='utf-8').read().splitlines():
        if not ln or ln.startswith('#') or '=' not in ln: continue
        k, v = ln.split('=', 1); p = v.split('|')
        idx = {'slot': (2, 3, 4, 5), 'opt': (3, 4), 'fix': (3, 4, 5, 6)}.get(k)
        if not idx or (k == 'slot' and len(p) < 6) or (k == 'opt' and len(p) < 6) or (k == 'fix' and len(p) < 7): continue
        for a in range(0, len(idx), 2):
            ru, en = p[idx[a]], p[idx[a + 1]]
            if en.strip() and re.search('[A-Za-z]', en): out.setdefault(en, (ru, 'gfx.txt'))
    return out

def from_help():
    out = {}
    for f in (os.path.join(ROOT, 'shared', 'help', 'graphics.txt'), os.path.join(ROOT, 'games', 'divine-divinity', 'gfx', 'help.txt')):
        ru = {}
        for ln in open(f, encoding='utf-8').read().splitlines():
            if ln.startswith('## '): ru = {}; continue
            if '=' not in ln or ln.startswith('#'): continue
            k, v = ln.split('=', 1); v = v.replace('\\n', '\n')
            if k in ('title.ru', 'ru'): ru[k] = v
            if k == 'title.en': out.setdefault(v, (ru.get('title.ru', ''), os.path.basename(f)))
            if k == 'en': out.setdefault(v, (ru.get('ru', ''), os.path.basename(f)))
    return out

if __name__ == '__main__':
    allv, sk = {}, []
    c, sk = from_cs(); allv.update(c)
    for d in (from_gfx(), from_help()):
        for k, v in d.items(): allv.setdefault(k, v)
    lst = [{'en': k, 'ru': v[0], 'src': v[1]} for k, v in allv.items()]
    os.makedirs(os.path.join(ROOT, 'scratch', 'ko'), exist_ok=True)
    json.dump(lst, open(os.path.join(ROOT, 'scratch', 'ko', 'en_strings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(sk, open(os.path.join(ROOT, 'scratch', 'ko', 'skipped_composed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('strings', len(lst), 'chars', sum(len(x['en']) for x in lst), 'skipped (composed with values)', len(sk))
