import json
import os
from collections import defaultdict


def build_visualization(test_cases_file, attack_file, promptfoo_classified_file, validation_results_file, output_html):
    with open(test_cases_file, 'r') as f:
        test_cases = json.load(f)
    with open(attack_file, 'r') as f:
        attack_cases = json.load(f)
    with open(promptfoo_classified_file, 'r') as f:
        promptfoo_cases = json.load(f)

    # Load validation results for confidence scores
    validation_map = {}
    flagged_cases = []
    if os.path.exists(validation_results_file):
        with open(validation_results_file, 'r') as f:
            validation_data = json.load(f)
        for r in validation_data.get("results", []):
            key = (r["source"], r["case_index"])
            validation_map[key] = r
            if r["verdict"] == "incorrect":
                # Enrich with user_input from original data
                if r["source"] == "generated" and r["case_index"] < len(test_cases):
                    r["user_input"] = test_cases[r["case_index"]].get("user_input", "")
                    r["condition"] = test_cases[r["case_index"]].get("condition", "")
                elif r["source"] == "promptfoo" and r["case_index"] < len(promptfoo_cases):
                    r["user_input"] = promptfoo_cases[r["case_index"]].get("user_input", "")
                    r["condition"] = promptfoo_cases[r["case_index"]].get("llm_reason", "")
                else:
                    r["user_input"] = ""
                    r["condition"] = ""
                flagged_cases.append(r)
        validation_metrics = validation_data.get("metrics", {})
    else:
        validation_metrics = {}

    # Tag sources and attach confidence
    for i, c in enumerate(test_cases):
        c['source'] = 'generated'
        c['_idx'] = i
        v = validation_map.get(("generated", i))
        if v:
            c['validation_confidence'] = v['confidence']
            c['validation_verdict'] = v['verdict']
            c['validation_predicted'] = v['predicted_label']
            c['validation_tier'] = v['evaluation_tier']
            c['validation_reason'] = v.get('reason', '')
        else:
            c['validation_confidence'] = None
            c['validation_verdict'] = None

    for i, c in enumerate(promptfoo_cases):
        c['source'] = 'promptfoo'
        c['_idx'] = i
        c['condition'] = c.get('llm_reason', '')
        v = validation_map.get(("promptfoo", i))
        if v:
            c['validation_confidence'] = v['confidence']
            c['validation_verdict'] = v['verdict']
            c['validation_predicted'] = v['predicted_label']
            c['validation_tier'] = v['evaluation_tier']
            c['validation_reason'] = v.get('reason', '')
        else:
            c['validation_confidence'] = None
            c['validation_verdict'] = None

    # Unpack ARES
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
                    'validation_confidence': None,
                    'validation_verdict': None,
                })

    all_cases = test_cases + ares_expanded + promptfoo_cases

    # Group by guidance -> condition
    grouped = defaultdict(lambda: defaultdict(list))
    for c in all_cases:
        guidance_key = c.get('guidance') or 'general_safety'
        condition_key = c.get('condition') or 'uncategorized'
        grouped[guidance_key][condition_key].append(c)

    # Build HTML
    html = generate_html(grouped, flagged_cases, validation_metrics)
    with open(output_html, 'w') as f:
        f.write(html)

    total = len(all_cases)
    num_guidances = len(grouped)
    print(f"Report generated: {output_html}")
    print(f"Total cases: {total}")
    print(f"Guidance groups: {num_guidances}")
    print(f"Flagged cases: {len(flagged_cases)}")


def generate_html(grouped, flagged_cases, validation_metrics):
    source_colors = {
        'generated': '#3b82f6',
        'ares': '#ef4444',
        'promptfoo': '#f59e0b',
    }
    label_colors = {
        'allow': '#10b981',
        'disallow': '#ef4444',
    }
    verdict_colors = {
        'correct': '#10b981',
        'incorrect': '#ef4444',
        'uncertain': '#f59e0b',
    }

    # === Build main test cases section ===
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

        condition_tabs = ""
        condition_bodies = ""
        for cond_idx, (condition, cases) in enumerate(sorted(conditions.items(), key=lambda x: -len(x[1]))):
            active_class = "active" if cond_idx == 0 else ""
            display = "block" if cond_idx == 0 else "none"
            cond_escaped = condition.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            cond_short = cond_escaped[:60] + ('...' if len(condition) > 60 else '')

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
                attack_type = c.get('attack_type', '')
                user_input = c['user_input'][:150] + ('...' if len(c['user_input']) > 150 else '')
                user_input_escaped = user_input.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                # Confidence and verdict
                conf = c.get('validation_confidence')
                verdict = c.get('validation_verdict')
                if conf is not None:
                    conf_str = f"{conf:.2f}"
                    v_color = verdict_colors.get(verdict, '#6b7280')
                    verdict_badge = f'<span class="badge-sm" style="background:{v_color}">{verdict}</span>'
                else:
                    conf_str = '-'
                    verdict_badge = '<span class="badge-sm" style="background:#6b7280">N/A</span>'

                rows += f"""<tr>
                    <td><span class="badge-sm" style="background:{src_color}">{c['source']}</span></td>
                    <td><span class="badge-sm" style="background:{lbl_color}">{c['label']}</span></td>
                    <td>{action}</td>
                    <td>{attack_type}</td>
                    <td class="user-input">{user_input_escaped}</td>
                    <td>{conf_str}</td>
                    <td>{verdict_badge}</td>
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
                            <th>Verdict</th>
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

    # === Build flagged cases section ===
    flagged_html = ""
    if flagged_cases:
        flagged_rows = ""
        for r in flagged_cases:
            src_color = source_colors.get(r['source'], '#6b7280')
            assigned_color = label_colors.get(r['assigned_label'], '#6b7280')
            predicted_color = label_colors.get(r['predicted_label'], '#6b7280')
            tier_badge = f'<span class="badge-sm" style="background:#6366f1">{r["evaluation_tier"]}</span>'
            reason_escaped = r.get('reason', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            guidance_short = (r.get('guidance', '')[:100] + '...') if len(r.get('guidance', '')) > 100 else r.get('guidance', '')
            guidance_escaped = guidance_short.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            user_input = r.get('user_input', '')
            user_input_short = (user_input[:200] + '...') if len(user_input) > 200 else user_input
            user_input_escaped = user_input_short.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            condition = r.get('condition', '')
            condition_escaped = condition.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            flagged_rows += f"""<tr>
                <td><span class="badge-sm" style="background:{src_color}">{r['source']}</span></td>
                <td><span class="badge-sm" style="background:{assigned_color}">{r['assigned_label']}</span></td>
                <td><span class="badge-sm" style="background:{predicted_color}">{r['predicted_label']}</span></td>
                <td>{r['confidence']:.2f}</td>
                <td>{tier_badge}</td>
                <td class="user-input-cell">{user_input_escaped}</td>
                <td class="condition-cell">{condition_escaped}</td>
                <td class="guidance-cell">{guidance_escaped}</td>
                <td class="reason-cell">{reason_escaped}</td>
            </tr>"""

        flagged_html = f"""
        <div class="flagged-section">
            <h2>Flagged Cases (Potential Mislabels)</h2>
            <p class="flagged-desc">These {len(flagged_cases)} cases have predicted labels that disagree with their assigned labels. Review these for potential test generation errors.</p>
            <table class="flagged-table">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Assigned</th>
                        <th>Predicted</th>
                        <th>Confidence</th>
                        <th>Tier</th>
                        <th>User Input</th>
                        <th>Condition</th>
                        <th>Guidance</th>
                        <th>Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {flagged_rows}
                </tbody>
            </table>
        </div>"""

    # === Summary stats ===
    all_flat = [c for conds in grouped.values() for cases in conds.values() for c in cases]
    total = len(all_flat)
    total_generated = sum(1 for c in all_flat if c['source'] == 'generated')
    total_ares = sum(1 for c in all_flat if c['source'] == 'ares')
    total_promptfoo = sum(1 for c in all_flat if c['source'] == 'promptfoo')
    total_allow = sum(1 for c in all_flat if c['label'] == 'allow')
    total_disallow = sum(1 for c in all_flat if c['label'] == 'disallow')

    # Validation summary
    overall = validation_metrics.get("overall", {})
    val_total = overall.get("total", 0)
    val_correct = overall.get("correct", 0)
    val_incorrect = overall.get("incorrect", 0)
    val_accuracy = overall.get("accuracy", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smith - Test Case Evaluation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; padding: 24px; color: #1e293b; }}
        .header {{ max-width: 1400px; margin: 0 auto 24px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 16px; }}
        .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
        .stat {{ background: white; border-radius: 8px; padding: 12px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
        .stat .value {{ font-size: 20px; font-weight: 600; }}
        .tabs-nav {{ display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0; padding-bottom: 0; }}
        .tab-btn {{ padding: 10px 20px; border: none; background: none; cursor: pointer; font-size: 14px; font-weight: 500; color: #64748b; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s; }}
        .tab-btn:hover {{ color: #1e293b; }}
        .tab-btn.active {{ color: #1e293b; border-bottom-color: #3b82f6; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
        .filter-btn {{ padding: 6px 14px; border-radius: 16px; border: 1px solid #e2e8f0; background: white; cursor: pointer; font-size: 13px; transition: all 0.2s; }}
        .filter-btn:hover {{ background: #f8fafc; }}
        .filter-btn.active {{ background: #1e293b; color: white; border-color: #1e293b; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
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
        .user-input {{ max-width: 400px; word-break: break-word; }}
        .flagged-section {{ max-width: 1400px; margin: 0 auto; }}
        .flagged-section h2 {{ font-size: 20px; margin-bottom: 8px; }}
        .flagged-desc {{ color: #64748b; margin-bottom: 16px; font-size: 14px; }}
        .flagged-table {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
        .flagged-table th {{ background: #fef2f2; }}
        .user-input-cell {{ max-width: 300px; word-break: break-word; font-size: 12px; }}
        .condition-cell {{ max-width: 200px; word-break: break-word; font-size: 12px; color: #6366f1; }}
        .guidance-cell {{ max-width: 250px; word-break: break-word; font-size: 12px; }}
        .reason-cell {{ max-width: 300px; word-break: break-word; font-size: 12px; color: #475569; }}
        .validation-summary {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .validation-summary h3 {{ font-size: 16px; margin-bottom: 12px; }}
        .val-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
        .val-stat {{ text-align: center; padding: 12px; background: #f8fafc; border-radius: 6px; }}
        .val-stat .val-num {{ font-size: 24px; font-weight: 700; }}
        .val-stat .val-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; margin-top: 4px; }}
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
            <div class="stat"><div class="label">Flagged</div><div class="value" style="color:#ef4444">{len(flagged_cases)}</div></div>
        </div>

        <div class="tabs-nav">
            <button class="tab-btn active" onclick="switchMainTab('tab-cases')">Test Cases</button>
            <button class="tab-btn" onclick="switchMainTab('tab-flagged')">Flagged Cases ({len(flagged_cases)})</button>
            <button class="tab-btn" onclick="switchMainTab('tab-validation')">Validation Summary</button>
        </div>
    </div>

    <div class="container">
        <div class="tab-content active" id="tab-cases">
            <div class="filters">
                <button class="filter-btn active" onclick="filterCards('all')">All</button>
                <button class="filter-btn" onclick="filterCards('generated')">Generated</button>
                <button class="filter-btn" onclick="filterCards('ares')">ARES</button>
                <button class="filter-btn" onclick="filterCards('promptfoo')">Promptfoo</button>
                <button class="filter-btn" onclick="filterCards('allow')">Allow</button>
                <button class="filter-btn" onclick="filterCards('disallow')">Disallow</button>
            </div>
            {cards_html}
        </div>

        <div class="tab-content" id="tab-flagged">
            {flagged_html if flagged_html else '<p style="color:#64748b;padding:20px;">No flagged cases. All labels appear correct.</p>'}
        </div>

        <div class="tab-content" id="tab-validation">
            <div class="validation-summary">
                <h3>Label Validation Results</h3>
                <div class="val-grid">
                    <div class="val-stat"><div class="val-num">{val_total}</div><div class="val-label">Evaluated</div></div>
                    <div class="val-stat"><div class="val-num" style="color:#10b981">{val_correct}</div><div class="val-label">Correct</div></div>
                    <div class="val-stat"><div class="val-num" style="color:#ef4444">{val_incorrect}</div><div class="val-label">Incorrect</div></div>
                    <div class="val-stat"><div class="val-num" style="color:#3b82f6">{val_accuracy:.1%}</div><div class="val-label">Accuracy</div></div>
                </div>
            </div>
            <div class="validation-summary">
                <h3>By Source</h3>
                <div class="val-grid">
                    {"".join(f'<div class="val-stat"><div class="val-num">{v.get("accuracy", 0):.1%}</div><div class="val-label">{k} (n={v.get("total", 0)})</div></div>' for k, v in validation_metrics.get("by_source", {}).items())}
                </div>
            </div>
            <div class="validation-summary">
                <h3>By Label</h3>
                <div class="val-grid">
                    {"".join(f'<div class="val-stat"><div class="val-num">{v.get("accuracy", 0):.1%}</div><div class="val-label">{k} (n={v.get("total", 0)})</div></div>' for k, v in validation_metrics.get("by_label", {}).items())}
                </div>
            </div>
            <div class="validation-summary">
                <h3>Tier Distribution</h3>
                <div class="val-grid">
                    {"".join(f'<div class="val-stat"><div class="val-num">{v}</div><div class="val-label">{k}</div></div>' for k, v in validation_metrics.get("tier_distribution", {}).items())}
                </div>
            </div>
        </div>
    </div>

    <script>
        function switchCondTab(btn, cardId, condId) {{
            const card = document.getElementById(cardId);
            card.querySelectorAll('.cond-tab').forEach(t => t.classList.remove('active'));
            card.querySelectorAll('.cond-body').forEach(b => b.style.display = 'none');
            btn.classList.add('active');
            document.getElementById(condId).style.display = 'block';
        }}

        function switchMainTab(tabId) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }}

        function filterCards(type) {{
            document.querySelectorAll('.filters .filter-btn').forEach(b => b.classList.remove('active'));
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
    base_url = os.getenv("BASE_URL", os.getenv("BASE_SKILL_URL", ""))
    build_visualization(
        base_url + "references/test_cases.json",
        base_url + "references/decomp_attack_file.json",
        base_url + "references/decomp_attack_file_promptfoo_classified.json",
        base_url + "references/label_validation_results.json",
        base_url + "references/test_case_report.html"
    )
