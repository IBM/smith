import json
import os
from collections import defaultdict


def build_visualization(test_cases_file, attack_file, promptfoo_classified_file, output_html):
    with open(test_cases_file, 'r') as f:
        test_cases = json.load(f)
    with open(attack_file, 'r') as f:
        attack_cases = json.load(f)
    with open(promptfoo_classified_file, 'r') as f:
        promptfoo_cases = json.load(f)

    # Tag sources
    for c in test_cases:
        c['source'] = 'generated'
    for c in promptfoo_cases:
        c['source'] = 'promptfoo'
        c['condition'] = c.get('llm_reason', '')

    # Unpack ARES: only disallow cases, expand attack_conditions into individual cases
    ares_expanded = []
    for c in attack_cases:
        if c['label'] != 'disallow':
            continue
        attack_conditions = c.get('attack_conditions', {})
        for attack_type, prompts in attack_conditions.items():
            for prompt in prompts:
                ares_expanded.append({
                    'source': 'ares',
                    'label': 'disallow',
                    'action': c.get('action', ''),
                    'guidance': c.get('guidance', ''),
                    'condition': c.get('condition', ''),
                    'user_input': prompt,
                    'attack_type': attack_type,
                })

    all_cases = test_cases + ares_expanded + promptfoo_cases

    # Group by guidance -> condition
    grouped = defaultdict(lambda: defaultdict(list))
    for c in all_cases:
        guidance_key = c.get('guidance') or 'general_safety'
        condition_key = c.get('condition') or 'uncategorized'
        grouped[guidance_key][condition_key].append(c)

    # Build HTML
    html = generate_html(grouped)
    with open(output_html, 'w') as f:
        f.write(html)

    total = len(all_cases)
    num_guidances = len(grouped)
    print(f"Report generated: {output_html}")
    print(f"Total cases: {total}")
    print(f"Guidance groups: {num_guidances}")


def generate_html(grouped):
    source_colors = {
        'generated': '#3b82f6',
        'ares': '#ef4444',
        'promptfoo': '#f59e0b',
    }
    label_colors = {
        'allow': '#10b981',
        'disallow': '#ef4444',
    }

    cards_html = ""
    card_idx = 0
    for guidance, conditions in sorted(grouped.items(), key=lambda x: -sum(len(v) for v in x[1].values())):
        all_cases_in_guidance = [c for cases in conditions.values() for c in cases]
        source_counts = defaultdict(int)
        label_counts = defaultdict(int)
        for c in all_cases_in_guidance:
            source_counts[c['source']] += 1
            label_counts[c['label']] += 1

        badges = ""
        for src, count in source_counts.items():
            color = source_colors.get(src, '#6b7280')
            badges += f'<span class="badge" style="background:{color}">{src}: {count}</span>'
        for lbl, count in label_counts.items():
            color = label_colors.get(lbl, '#6b7280')
            badges += f'<span class="badge" style="background:{color}">{lbl}: {count}</span>'

        # Build condition sub-tabs
        condition_tabs = ""
        condition_bodies = ""
        for cond_idx, (condition, cases) in enumerate(sorted(conditions.items(), key=lambda x: -len(x[1]))):
            active_class = "active" if cond_idx == 0 else ""
            display = "block" if cond_idx == 0 else "none"
            cond_escaped = condition.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            cond_short = cond_escaped[:60] + ('...' if len(condition) > 60 else '')

            # Determine condition color based on cases' labels
            case_labels = set(c['label'] for c in cases)
            if case_labels == {'allow'}:
                cond_color_class = "cond-allow"
            elif case_labels == {'disallow'}:
                cond_color_class = "cond-disallow"
            else:
                cond_color_class = "cond-mixed"

            condition_tabs += f'<button class="cond-tab {active_class} {cond_color_class}" onclick="switchCondTab(this, \'card{card_idx}\', \'cond{card_idx}_{cond_idx}\')">{cond_short} <span class="cond-count">({len(cases)})</span></button>'

            rows = ""
            for c in cases:
                src_color = source_colors.get(c['source'], '#6b7280')
                lbl_color = label_colors.get(c['label'], '#6b7280')
                action = c.get('action', 'N/A')
                confidence = c.get('confidence', '')
                confidence_str = f"{confidence:.3f}" if isinstance(confidence, float) else ''
                attack_type = c.get('attack_type', '')
                user_input = c['user_input'][:150] + ('...' if len(c['user_input']) > 150 else '')
                user_input_escaped = user_input.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                rows += f"""<tr>
                    <td><span class="badge-sm" style="background:{src_color}">{c['source']}</span></td>
                    <td><span class="badge-sm" style="background:{lbl_color}">{c['label']}</span></td>
                    <td>{action}</td>
                    <td>{attack_type}</td>
                    <td class="user-input">{user_input_escaped}</td>
                    <td>{confidence_str}</td>
                </tr>"""

            condition_bodies += f"""<div class="cond-body" id="cond{card_idx}_{cond_idx}" style="display:{display}">
                <table>
                    <thead>
                        <tr>
                            <th>Source</th>
                            <th>Label</th>
                            <th>Action</th>
                            <th>Attack Type</th>
                            <th>User Input</th>
                            <th>Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>"""

        guidance_escaped = guidance.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        cards_html += f"""
        <div class="card" id="card{card_idx}">
            <div class="card-header" onclick="this.parentElement.classList.toggle('expanded')">
                <div class="card-title">
                    <span class="arrow">&#9654;</span>
                    <span class="guidance-text">{guidance_escaped}</span>
                </div>
                <div class="card-badges">
                    {badges}
                    <span class="badge" style="background:#6b7280">total: {len(all_cases_in_guidance)}</span>
                </div>
            </div>
            <div class="card-body">
                <div class="cond-tabs">
                    {condition_tabs}
                </div>
                <div class="cond-content">
                    {condition_bodies}
                </div>
            </div>
        </div>"""
        card_idx += 1

    # Summary stats
    all_flat = [c for conds in grouped.values() for cases in conds.values() for c in cases]
    total = len(all_flat)
    total_generated = sum(1 for c in all_flat if c['source'] == 'generated')
    total_ares = sum(1 for c in all_flat if c['source'] == 'ares')
    total_promptfoo = sum(1 for c in all_flat if c['source'] == 'promptfoo')
    total_allow = sum(1 for c in all_flat if c['label'] == 'allow')
    total_disallow = sum(1 for c in all_flat if c['label'] == 'disallow')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smith - Test Case Evaluation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; padding: 24px; color: #1e293b; }}
        .header {{ max-width: 1200px; margin: 0 auto 24px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 16px; }}
        .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
        .stat {{ background: white; border-radius: 8px; padding: 12px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
        .stat .value {{ font-size: 20px; font-weight: 600; }}
        .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
        .filter-btn {{ padding: 6px 14px; border-radius: 16px; border: 1px solid #e2e8f0; background: white; cursor: pointer; font-size: 13px; transition: all 0.2s; }}
        .filter-btn:hover {{ background: #f8fafc; }}
        .filter-btn.active {{ background: #1e293b; color: white; border-color: #1e293b; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
        .card-header {{ padding: 14px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 12px; }}
        .card-header:hover {{ background: #f8fafc; }}
        .card-title {{ display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }}
        .arrow {{ font-size: 12px; color: #94a3b8; transition: transform 0.2s; }}
        .card.expanded .arrow {{ transform: rotate(90deg); }}
        .guidance-text {{ font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .card-badges {{ display: flex; gap: 6px; flex-shrink: 0; }}
        .badge {{ font-size: 11px; padding: 3px 8px; border-radius: 10px; color: white; font-weight: 500; }}
        .badge-sm {{ font-size: 11px; padding: 2px 6px; border-radius: 8px; color: white; font-weight: 500; }}
        .card-body {{ display: none; padding: 0 20px 16px; }}
        .card.expanded .card-body {{ display: block; }}
        .cond-tabs {{ display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 12px; padding-top: 8px; }}
        .cond-tab {{ padding: 5px 12px; border-radius: 6px; border: 1px solid #e2e8f0; background: #f8fafc; cursor: pointer; font-size: 12px; transition: all 0.2s; }}
        .cond-tab:hover {{ opacity: 0.8; }}
        .cond-tab.cond-allow {{ background: #d1fae5; border-color: #6ee7b7; color: #065f46; }}
        .cond-tab.cond-disallow {{ background: #fee2e2; border-color: #fca5a5; color: #991b1b; }}
        .cond-tab.cond-mixed {{ background: #fef3c7; border-color: #fcd34d; color: #92400e; }}
        .cond-tab.active {{ background: #1e293b; color: white; border-color: #1e293b; }}
        .cond-count {{ opacity: 0.7; }}
        .cond-body {{ }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ text-align: left; padding: 8px 6px; border-bottom: 2px solid #e2e8f0; color: #64748b; font-weight: 600; }}
        td {{ padding: 8px 6px; border-bottom: 1px solid #f1f5f9; }}
        .user-input {{ max-width: 500px; word-break: break-word; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Smith - Test Case Evaluation Report</h1>
        <div class="summary">
            <div class="stat"><div class="label">Total Cases</div><div class="value">{total}</div></div>
            <div class="stat"><div class="label">Guidance Groups</div><div class="value">{len(grouped)}</div></div>
            <div class="stat"><div class="label">Generated</div><div class="value" style="color:#3b82f6">{total_generated}</div></div>
            <div class="stat"><div class="label">ARES</div><div class="value" style="color:#ef4444">{total_ares}</div></div>
            <div class="stat"><div class="label">Promptfoo</div><div class="value" style="color:#f59e0b">{total_promptfoo}</div></div>
            <div class="stat"><div class="label">Allow</div><div class="value" style="color:#10b981">{total_allow}</div></div>
            <div class="stat"><div class="label">Disallow</div><div class="value" style="color:#ef4444">{total_disallow}</div></div>
        </div>
        <div class="filters">
            <button class="filter-btn active" onclick="filterCards('all')">All</button>
            <button class="filter-btn" onclick="filterCards('generated')">Generated</button>
            <button class="filter-btn" onclick="filterCards('ares')">ARES</button>
            <button class="filter-btn" onclick="filterCards('promptfoo')">Promptfoo</button>
            <button class="filter-btn" onclick="filterCards('allow')">Allow</button>
            <button class="filter-btn" onclick="filterCards('disallow')">Disallow</button>
        </div>
    </div>
    <div class="container">
        {cards_html}
    </div>
    <script>
        function switchCondTab(btn, cardId, condId) {{
            const card = document.getElementById(cardId);
            card.querySelectorAll('.cond-tab').forEach(t => t.classList.remove('active'));
            card.querySelectorAll('.cond-body').forEach(b => b.style.display = 'none');
            btn.classList.add('active');
            document.getElementById(condId).style.display = 'block';
        }}

        function filterCards(type) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('table tbody tr').forEach(row => {{
                if (type === 'all') {{
                    row.style.display = '';
                }} else {{
                    const source = row.querySelector('td:first-child .badge-sm')?.textContent || '';
                    const label = row.querySelector('td:nth-child(2) .badge-sm')?.textContent || '';
                    if (source === type || label === type) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>"""
    return html


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    base_url = os.getenv("BASE_URL")
    build_visualization(
        base_url + "references/test_cases.json",
        base_url + "references/decomp_attack_file.json",
        base_url + "references/decomp_attack_file_promptfoo_classified.json",
        base_url + "references/test_case_report.html"
    )
