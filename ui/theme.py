"""Navy-inspired design tokens (colours, type, square corners). Tokens only. No template code
or assets are reused."""
import gradio as gr

HEAD = """
<script>
/* Navy is a light design: pin Gradio to its light theme regardless of OS setting */
(function () {
  var u = new URL(window.location.href);
  if (u.searchParams.get('__theme') !== 'light') { u.searchParams.set('__theme', 'light'); window.location.replace(u.href); }
})();
</script>
<link rel="preconnect" href="https://api.fontshare.com">
<link href="https://api.fontshare.com/v2/css?f[]=switzer@400,500,600,700&display=swap" rel="stylesheet">
"""

THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.indigo,
    neutral_hue=gr.themes.colors.slate,
    radius_size=gr.themes.sizes.radius_none,
    font=["Switzer", "Inter", "system-ui", "sans-serif"],
    font_mono=["JetBrains Mono", "ui-monospace", "monospace"],
).set(
    body_background_fill="#FAFBFF",
    body_text_color="#111428",
    block_background_fill="#FFFFFF",
    block_border_color="#E3E7F7",
    block_label_text_color="#585D6F",
    block_title_text_color="#111428",
    input_background_fill="#FFFFFF",
    input_border_color="#D9DEF2",
    button_primary_background_fill="#DBDFFF",
    button_primary_background_fill_hover="#C9CFFF",
    button_primary_text_color="#111428",
    button_secondary_background_fill="#EAEEFC",
    button_secondary_text_color="#111428",
    shadow_drop="none",
    shadow_drop_lg="none",
    block_shadow="none",
)

CSS = """
:root { --ink:#111428; --muted:#585D6F; --surface:#EAEEFC; --line:#E3E7F7; --bg:#FAFBFF; --accent:#DBDFFF;
  --ok:#1F7A4D; --ask:#2F4DD9; --defer:#9A6B00; --esc:#C2410C; --no:#B42318; }
body, .gradio-container { background: var(--bg) !important; font-family: Switzer, Inter, system-ui, sans-serif !important; }
.gradio-container { max-width: 1240px !important; }
.de-eyebrow { font: 500 12px/1 'JetBrains Mono', ui-monospace, monospace; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin: 0 0 10px; }
.de-hero h1 { font-size: clamp(30px, 4.4vw, 48px); line-height:1.05; letter-spacing:-.02em; color:var(--ink); margin: 6px 0 12px; font-weight:600; }
.de-hero h1 em { font-style: italic; font-weight: 500; }
.de-hero p { color: var(--muted); font-size: 16px; max-width: 760px; margin: 0; }
.de-stats { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); border:1px solid var(--line); margin-top:22px; background:#fff; }
.de-stats > div { padding:16px 18px; border-right:1px solid var(--line); }
.de-stats > div:last-child { border-right:0; }
.de-stats b { display:block; font-size: 28px; font-weight:600; color: var(--ink); letter-spacing:-.02em; }
.de-stats span { color: var(--muted); font-size: 13px; }
.de-outcome { border:1px solid var(--line); background:#fff; padding:20px 22px; }
.de-badge { display:inline-block; font: 600 13px/1 'JetBrains Mono', monospace; letter-spacing:.12em; text-transform:uppercase; padding:9px 12px; color:#fff; }
.de-execute{background:var(--ok)} .de-ask{background:var(--ask)} .de-defer{background:var(--defer)} .de-escalate{background:var(--esc)} .de-refuse{background:var(--no)}
.de-outcome h2 { font-size: 22px; font-weight:600; margin: 14px 0 6px; color: var(--ink); }
.de-outcome .next { color: var(--muted); margin: 0; }
.de-grid { display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); border:1px solid var(--line); border-top:0; background:#fff; }
.de-grid > div { padding:14px 16px; border-right:1px solid var(--line); min-width:0; }
.de-grid > div:last-child { border-right:0; }
.de-grid .k { font: 500 11px/1.2 'JetBrains Mono', monospace; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
.de-grid .v { font-size: clamp(16px, 1.9vw, 24px); font-weight:600; margin: 6px 0 4px; color:var(--ink); letter-spacing:-.02em; overflow-wrap:anywhere; }
.de-grid .s { font-size: 12px; color: var(--muted); overflow-wrap:anywhere; }
.de-bar { height:4px; background: var(--surface); margin-top:8px; } .de-bar i { display:block; height:4px; background: var(--ink); }
.de-section { margin-top: 22px; }
.de-timeline { list-style:none; margin:0; padding:0; border-left:1px solid var(--line); }
.de-timeline li { position:relative; padding: 0 0 16px 22px; }
.de-timeline li::before { content:''; position:absolute; left:-5px; top:5px; width:9px; height:9px; background:#fff; border:1px solid var(--muted); }
.de-timeline li.hit::before { background: var(--ink); border-color: var(--ink); }
.de-timeline .t { font: 500 12px 'JetBrains Mono', monospace; color: var(--muted); margin-right:8px; }
.de-timeline .g { font-weight:600; text-transform: capitalize; }
.de-timeline .r { color: var(--muted); font-size: 13px; margin-top:3px; }
.de-table { width:100%; border-collapse: collapse; background:#fff; border:1px solid var(--line); font-size:13px; }
.de-table th, .de-table td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; }
.de-table th { font: 500 11px 'JetBrains Mono', monospace; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); background: var(--bg); }
.de-yes { color: var(--ok); font-weight:600; } .de-no { color: var(--no); font-weight:600; }
.de-chip { display:inline-block; font: 500 11px 'JetBrains Mono', monospace; padding:3px 7px; background: var(--surface); margin: 2px 4px 2px 0; }
.de-chip.warn { background:#FDECEC; color: var(--no); }
.de-flow { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); border:1px solid var(--line); background:#fff; }
.de-flow > div { padding:18px; border-right:1px solid var(--line); }
.de-flow > div:last-child { border-right:0; }
.de-flow h3 { margin: 4px 0 8px; font-size: 18px; } .de-flow p { color: var(--muted); font-size: 13px; margin:0; }
@media (max-width: 760px) {
  .de-grid, .de-stats, .de-flow { grid-template-columns: 1fr 1fr; }
  .de-grid > div, .de-stats > div, .de-flow > div { border-bottom:1px solid var(--line); }
}
"""
