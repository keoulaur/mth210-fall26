#!/usr/bin/env python3
"""
ldk_convert.py — Convert LDK-style (Keough) LaTeX to PreTeXt XML.
Usage: python ldk_convert.py latex/FILENAME.tex
Output: source/activities/FILENAME.ptx
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ── preamble / comment stripping ─────────────────────────────────────────────

def strip_preamble(tex):
    m = re.search(r'\\begin\{document\}', tex)
    if not m:
        return tex
    after = tex[m.end():]
    m2 = re.search(r'\\end\{document\}', after)
    return after[:m2.start()] if m2 else after

# ── environment utilities ─────────────────────────────────────────────────────

def find_env(text, env, start=0):
    """Find \\begin{env}...\\end{env} with depth tracking.
    Returns (begin_pos, end_pos, inner) or None."""
    bp = re.compile(r'\\begin\{' + re.escape(env) + r'\}')
    ep = re.compile(r'\\end\{' + re.escape(env) + r'\}')
    m = bp.search(text, start)
    if not m:
        return None
    depth = 1
    i = m.end()
    while i < len(text) and depth > 0:
        mb = bp.search(text, i)
        me = ep.search(text, i)
        if me is None:
            return None
        if mb and mb.start() < me.start():
            depth += 1
            i = mb.end()
        else:
            depth -= 1
            if depth == 0:
                return (m.start(), me.end(), text[m.end():me.start()])
            i = me.end()
    return None

def split_items(text):
    """Split enumerate/itemize content into \\item chunks at depth 0."""
    items = []
    depth = 0
    start = None
    i = 0
    while i < len(text):
        m = re.match(r'\\begin\{(?:enumerate|itemize)\}', text[i:])
        if m:
            depth += 1
            i += len(m.group(0))
            continue
        m = re.match(r'\\end\{(?:enumerate|itemize)\}', text[i:])
        if m:
            depth -= 1
            i += len(m.group(0))
            continue
        m = re.match(r'\\item(?:\[[^\]]*\])?\s*', text[i:])
        if m and depth == 0:
            if start is not None:
                items.append(text[start:i])
            start = i + len(m.group(0))
            i = start
            continue
        i += 1
    if start is not None:
        items.append(text[start:])
    return items

# ── math / text conversion ────────────────────────────────────────────────────

def escape_math(s):
    s = s.replace('&', r'\amp ')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s

def escape_xml(s):
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s

def convert_text(text):
    """Convert a LaTeX text chunk to a PreTeXt XML string (no <p> wrapping)."""
    # Extract \[...\] and $$...$$ display math
    dmath = {}
    def save_dm(m):
        k = f'\x00DM{len(dmath)}\x00'
        dmath[k] = '<md>' + escape_math(m.group(1).strip()) + '</md>'
        return k
    text = re.sub(r'\\\[(.*?)\\\]', save_dm, text, flags=re.DOTALL)
    text = re.sub(r'\$\$(.*?)\$\$', save_dm, text, flags=re.DOTALL)

    # Extract $...$ inline math
    imath = {}
    def save_im(m):
        k = f'\x00IM{len(imath)}\x00'
        imath[k] = '<m>' + escape_math(m.group(1)) + '</m>'
        return k
    text = re.sub(r'\$([^$]+?)\$', save_im, text)

    # Escape XML special chars in plain text
    text = escape_xml(text)

    # \emph{} and {\em ...}
    text = re.sub(r'\\emph\{([^}]*)\}', r'<em>\1</em>', text)
    text = re.sub(r'\{\\em\s+([^}]*)\}', r'<em>\1</em>', text)

    # {\bf text} → <term> (must come before general noise removal)
    text = re.sub(r'\{\\bf\s*\{?([^{}]+?)\}?\}', r'<term>\1</term>', text)
    text = re.sub(r'\\textbf\{([^}]+)\}', r'<term>\1</term>', text)

    # \url{...} must come before \footnote so nested \url inside \footnote works
    text = re.sub(r'\\url\{([^}]+)\}', r'<url href="\1">\1</url>', text)

    # \footnote{...} → <fn>...</fn>
    text = re.sub(r'\\footnote\{([^}]*)\}', r'<fn>\1</fn>', text)

    # \underline{\hspace{...}} → fill-in blank placeholder
    text = re.sub(r'\\underline\{\\hspace\*?\{[^}]*\}\}', '_____', text)
    # \underline{text} → just the text
    text = re.sub(r'\\underline\{([^}]*)\}', r'\1', text)

    # Strip noise commands
    text = re.sub(
        r'\\(?:noindent|nin|newpage|clearpage|vfill|hfill|centering'
        r'|medskip|bigskip|smallskip|pagebreak)\b', '', text)
    text = re.sub(r'\\(?:hspace|vspace)\*?\{[^}]*\}', '', text)
    text = re.sub(r'\\(?:markboth|pagestyle|thispagestyle|label|markright)'
                  r'\{[^}]*\}(?:\{[^}]*\})?', '', text)
    text = re.sub(r'\\setcounter\{[^}]*\}\{[^}]*\}', '', text)
    text = re.sub(r'\\\\', ' ', text)   # LaTeX line breaks → space

    # Restore math placeholders
    for k, v in dmath.items():
        text = text.replace(k, v)
    for k, v in imath.items():
        text = text.replace(k, v)

    return text.strip()

def strip_command(text, cmd):
    """Remove all \\cmd{...} occurrences, handling nested braces."""
    pat = re.compile(r'\\' + re.escape(cmd) + r'\s*\{')
    result = []
    i = 0
    while True:
        m = pat.search(text, i)
        if m is None:
            result.append(text[i:])
            break
        result.append(text[i:m.start()])
        j = m.end()
        depth = 1
        while j < len(text) and depth > 0:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
            j += 1
        i = j
    return ''.join(result)

def _parse_col_spec(spec):
    cols = []
    i = 0
    while i < len(spec):
        ch = spec[i]
        if ch in 'lcr':
            cols.append([{'l': 'left', 'c': 'center', 'r': 'right'}[ch], False])
            i += 1
        elif ch == '|':
            while i < len(spec) and spec[i] == '|':
                i += 1
            if cols:
                cols[-1][1] = True
        elif ch == 'p':
            i += 1
            if i < len(spec) and spec[i] == '{':
                depth, i = 1, i + 1
                while i < len(spec) and depth > 0:
                    if spec[i] == '{': depth += 1
                    elif spec[i] == '}': depth -= 1
                    i += 1
            cols.append(['left', False])
        else:
            i += 1
    return [(align, has_right) for align, has_right in cols]

def convert_tabular(col_spec, inner):
    cols = list(_parse_col_spec(col_spec))
    if cols:
        cols[-1] = (cols[-1][0], False)   # no right border on last column
    lines = ['<tabular>']
    for align, has_right in cols:
        right_attr = ' right="minor"' if has_right else ''
        lines.append(f'  <col halign="{align}"{right_attr}/>')
    processed = []
    for chunk in re.split(r'\\\\', inner):
        stripped = chunk.strip()
        if re.match(r'\\hline', stripped) and processed:
            processed[-1][1] = True
        row_text = re.sub(r'\\hline', '', chunk)
        row_text = re.sub(r'\\cline\{[^}]+\}', '', row_text).strip()
        if row_text:
            processed.append([row_text, False])
    if processed:
        processed[-1][1] = False   # no bottom border on last row
    for row_text, has_bottom in processed:
        bottom_attr = ' bottom="minor"' if has_bottom else ''
        lines.append(f'  <row{bottom_attr}>')
        for cell in row_text.split('&'):
            lines.append(f'    <cell>{convert_text(cell.strip())}</cell>')
        lines.append('  </row>')
    lines.append('</tabular>')
    return '\n'.join(lines)

def chunk_to_ptx(text, indent='    '):
    """Convert a block of LaTeX text to PreTeXt XML lines (<p>, <ul>, <ol>).
    Handles embedded itemize/enumerate and strips unsupported environments."""
    # Strip wrappers that don't add structure
    text = re.sub(r'\\begin\{center\}|\\end\{center\}', '', text)
    text = strip_command(text, 'boxed')

    # Remove environments we can't meaningfully convert
    for env in ('tikzpicture', 'minipage', 'multicols', 'verbatim', 'comment'):
        text = re.sub(
            r'\\begin\{' + env + r'\}.*?\\end\{' + env + r'\}',
            '', text, flags=re.DOTALL)

    lines = []
    i = 0
    block_pat = re.compile(r'\\begin\{(itemize|enumerate|tabular)\}')

    while i < len(text):
        m = block_pat.search(text, i)
        if m:
            before = text[i:m.start()].strip()
            if before:
                for para in re.split(r'\n\s*\n', before):
                    p = convert_text(para).strip()
                    if p:
                        lines.append(f'{indent}<p>{p}</p>')

            env = m.group(1)
            if env == 'tabular':
                tm = re.match(
                    r'\\begin\{tabular\}\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}(.*?)\\end\{tabular\}',
                    text[m.start():], flags=re.DOTALL)
                if tm:
                    lines.append(convert_tabular(tm.group(1), tm.group(2)))
                    i = m.start() + tm.end()
                else:
                    i = m.end()
            else:
                r = find_env(text, env, m.start())
                if r:
                    _, end_pos, inner = r
                    tag = 'ul' if env == 'itemize' else 'ol'
                    lines.append(f'{indent}<{tag}>')
                    for item in split_items(inner):
                        p = convert_text(item.strip()).strip()
                        if p:
                            lines.append(f'{indent}  <li><p>{p}</p></li>')
                    lines.append(f'{indent}</{tag}>')
                    i = end_pos
                else:
                    i = m.end()
        else:
            remaining = text[i:].strip()
            if remaining:
                for para in re.split(r'\n\s*\n', remaining):
                    p = convert_text(para).strip()
                    if p:
                        lines.append(f'{indent}<p>{p}</p>')
            break

    return lines

# ── theorem-like environments ─────────────────────────────────────────────────

ENV_MAP = {
    'defn':        'definition',
    'theorem':     'theorem',
    'proposition': 'proposition',
    'lemma':       'lemma',
    'corollary':   'corollary',
    'conjecture':  'conjecture',
    'prin':        'principle',
}

def build_thm(env, inner, opt_title='', indent='  '):
    ptx = ENV_MAP.get(env, env)
    lines = [f'{indent}<{ptx}>']
    if opt_title:
        lines.append(f'{indent}  <title>{convert_text(opt_title)}</title>')
    lines.append(f'{indent}  <statement>')
    lines.extend(chunk_to_ptx(inner, indent + '    '))
    lines.append(f'{indent}  </statement>')
    lines.append(f'{indent}</{ptx}>')
    return lines

def build_proof(inner, indent='  '):
    lines = [f'{indent}<proof>']
    lines.extend(chunk_to_ptx(inner, indent + '  '))
    lines.append(f'{indent}</proof>')
    return lines

# ── activity / exercise ───────────────────────────────────────────────────────

def build_activity(label_text, body_text, indent='  '):
    """Build an <exercise> from a {\bf Activity...} block."""
    # Strip environments we can't convert from the body
    for env in ('tikzpicture', 'minipage', 'multicols'):
        body_text = re.sub(
            r'\\begin\{' + env + r'\}.*?\\end\{' + env + r'\}',
            '', body_text, flags=re.DOTALL)
    body_text = re.sub(r'\\begin\{center\}|\\end\{center\}', '', body_text)

    enum_r = find_env(body_text, 'enumerate')
    ws_attr = '' if enum_r else ' workspace="1in"'
    lines = [f'{indent}<activity{ws_attr}>']

    if enum_r:
        eb, ee, inner = enum_r
        pre = (label_text + '\n\n' + body_text[:eb]).strip()
        if pre:
            lines.append(f'{indent}  <introduction>')
            lines.extend(chunk_to_ptx(pre, indent + '    '))
            lines.append(f'{indent}  </introduction>')

        for item in split_items(inner):
            has_vfill = bool(re.search(r'\\vfill', item))
            ws = ' workspace="1in"' if has_vfill else ''
            item_clean = re.sub(r'\\vfill', '', item).strip()

            # Nested enumerate → sub-tasks
            nested = find_env(item_clean, 'enumerate')
            if nested:
                nb, ne, ninner = nested
                item_intro = item_clean[:nb].strip()
                lines.append(f'{indent}  <task{ws}>')
                if item_intro:
                    lines.append(f'{indent}    <introduction>')
                    lines.extend(chunk_to_ptx(item_intro, indent + '      '))
                    lines.append(f'{indent}    </introduction>')
                for sub in split_items(ninner):
                    sub_clean = re.sub(r'\\vfill', '', sub).strip()
                    lines.append(f'{indent}    <task>')
                    lines.append(f'{indent}      <statement>')
                    lines.extend(chunk_to_ptx(sub_clean, indent + '        '))
                    lines.append(f'{indent}      </statement>')
                    lines.append(f'{indent}    </task>')
                lines.append(f'{indent}  </task>')
            else:
                lines.append(f'{indent}  <task{ws}>')
                lines.append(f'{indent}    <statement>')
                lines.extend(chunk_to_ptx(item_clean, indent + '      '))
                lines.append(f'{indent}    </statement>')
                lines.append(f'{indent}  </task>')
    else:
        # No enumerate — single statement
        full = (label_text + '\n\n' + body_text).strip()
        lines.append(f'{indent}  <statement>')
        lines.extend(chunk_to_ptx(full, indent + '    '))
        lines.append(f'{indent}  </statement>')

    lines.append(f'{indent}</activity>')
    return lines

# ── structural marker patterns ────────────────────────────────────────────────

_SECTION_RE    = re.compile(r'\\section\*?\{([^}]*)\}')
_SUBSECTION_RE = re.compile(r'\\subsection\*?\{([^}]*)\}')
_ACTIVITY_RE   = re.compile(r'(?:\\nin\s*)?\{\\bf\s+Activity[^}]*\}')
_THM_BEGIN_RE  = re.compile(
    r'\\begin\{(defn|theorem|proposition|lemma|corollary|conjecture|prin)\}'
    r'(?:\[([^\]]*)\])?'
)
_PROOF_BEGIN_RE = re.compile(r'\\begin\{proof\}')

# Any pattern that ends an activity body
_NEXT_MARKER_RE = re.compile(
    r'\\section\*?\{[^}]*\}'
    r'|\\subsection\*?\{[^}]*\}'
    r'|(?:\\nin\s*)?\{\\bf\s+Activity[^}]*\}'
    r'|\\begin\{(?:defn|theorem|proposition|lemma|corollary|conjecture|prin|proof)\}'
)

# ── main body processor ───────────────────────────────────────────────────────

def process_body(text):
    """Process the document body into a list of PreTeXt XML lines."""
    out = []
    pending = []
    # in_subsection tracks whether a <subsection> is currently open
    in_subsection = [False]

    def flush_pending():
        chunk = ''.join(pending).strip()
        pending.clear()
        if not chunk:
            return
        ind = '    ' if in_subsection[0] else '  '
        out.extend(chunk_to_ptx(chunk, ind))

    def open_subsection(title):
        flush_pending()
        if in_subsection[0]:
            out.append('  </subsection>')
        out.append('  <subsection>')
        out.append(f'    <title>{convert_text(title)}</title>')
        in_subsection[0] = True

    # Later \section* also become <subsection> since <section> cannot
    # contain <section> in PreTeXt.
    open_section = open_subsection

    i = 0
    while i < len(text):
        # \section*{title}
        m = re.match(r'\\section\*?\{([^}]*)\}', text[i:])
        if m:
            open_section(m.group(1))
            i += len(m.group(0))
            continue

        # \subsection*{title}
        m = re.match(r'\\subsection\*?\{([^}]*)\}', text[i:])
        if m:
            open_subsection(m.group(1))
            i += len(m.group(0))
            continue

        # {\bf Activity...}
        m = re.match(r'(?:\\nin\s*)?\{\\bf\s+Activity[^}]*\}', text[i:])
        if m:
            flush_pending()
            j = i + len(m.group(0))
            end_m = _NEXT_MARKER_RE.search(text, j)
            body = text[j:end_m.start()] if end_m else text[j:]
            next_i = end_m.start() if end_m else len(text)
            ind = '    ' if in_subsection[0] else '  '
            out.extend(build_activity('', body, ind))
            i = next_i
            continue

        # Theorem-like environments
        m = re.match(
            r'\\begin\{(defn|theorem|proposition|lemma|corollary|conjecture|prin)\}'
            r'(?:\[([^\]]*)\])?',
            text[i:])
        if m:
            flush_pending()
            env, opt_title = m.group(1), m.group(2) or ''
            r = find_env(text, env, i)
            if r:
                _, end_pos, inner = r
                ind = '    ' if in_subsection[0] else '  '
                out.extend(build_thm(env, inner, opt_title, ind))
                i = end_pos
                continue

        # proof
        if re.match(r'\\begin\{proof\}', text[i:]):
            flush_pending()
            r = find_env(text, 'proof', i)
            if r:
                _, end_pos, inner = r
                ind = '    ' if in_subsection[0] else '  '
                out.extend(build_proof(inner, ind))
                i = end_pos
                continue

        pending.append(text[i])
        i += 1

    flush_pending()
    if in_subsection[0]:
        out.append('  </subsection>')

    return out

# ── entry point ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print('Usage: ldk_convert.py latex/FILENAME.tex', file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).parent
    input_path = Path(sys.argv[1])
    if not input_path.is_absolute():
        input_path = script_dir / input_path

    tex = input_path.read_text(encoding='utf-8')
    body = strip_preamble(tex)

    # Strip LaTeX comments before any structural parsing
    body = re.sub(r'(?<!\\)%.*', '', body, flags=re.MULTILINE)

    # Extract title from first \section* (or \section)
    m = re.search(r'\\section\*?\{([^}]*)\}', body)
    if m:
        title = convert_text(m.group(1).strip())
        body = body[m.end():]
    else:
        title = input_path.stem

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<worksheet>',
        f'  <title>{title}</title>',
    ]
    xml_lines.extend(process_body(body))
    xml_lines.append('</worksheet>')

    xml_str = '\n'.join(xml_lines) + '\n'

    try:
        ET.fromstring(xml_str.encode('utf-8'))
    except ET.ParseError as e:
        print(f'WARNING: XML validation failed: {e}', file=sys.stderr)

    out_dir = script_dir / 'source' / 'activities'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (input_path.stem + '.ptx')
    out_path.write_text(xml_str, encoding='utf-8')
    print(f'Written: {out_path}')

if __name__ == '__main__':
    main()
