# Plots for the Gemini-hard catalogs: the catalog pipeline's plots on the selected tasks (Gemini models only), plus Argon difficulty plots.
import json, sys, matplotlib
matplotlib.use('svg')
import matplotlib.pyplot as plt, seaborn as sns, pandas as pd, numpy as np
from matplotlib import font_manager
import os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/catalog/assets'
FONTS = '/Users/carlos/code/sdlc_final_samples/catalogs/site/fonts'
for f in ('Inter-Regular.ttf', 'Inter-Medium.ttf', 'Inter-SemiBold.ttf'):
    try: font_manager.fontManager.addfont(f'{FONTS}/{f}')
    except Exception: pass
PAPER, INK, INK2, MUTED, LINE, LINE2, RED, TEAL = '#f7f4ed', '#11484e', '#446b6e', '#625f5d', '#cfcac2', '#e3ded5', '#f44029', '#1f6f6a'
TEAL_WASH, RED_WASH, CARD = (31 / 255, 111 / 255, 106 / 255, 0.09), (244 / 255, 64 / 255, 41 / 255, 0.08), '#fbf9f4'
plt.rcParams.update({
    'font.family': ['Inter', 'Arial', 'DejaVu Sans'], 'font.size': 10, 'svg.fonttype': 'path',
    'figure.facecolor': PAPER, 'axes.facecolor': PAPER, 'savefig.facecolor': PAPER,
    'axes.edgecolor': INK, 'axes.linewidth': 0.9, 'axes.labelcolor': MUTED, 'axes.labelsize': 9.5,
    'xtick.color': MUTED, 'ytick.color': INK, 'xtick.labelsize': 9, 'ytick.labelsize': 10,
    'axes.grid': True, 'grid.color': LINE2, 'grid.linewidth': 0.8, 'axes.axisbelow': True,
    'axes.spines.top': False, 'axes.spines.right': False, 'xtick.major.size': 0, 'ytick.major.size': 0,
})
S = json.loads(open(f'{H}/cat/stats.json').read().replace('Mid' + chr(92) + 'u2013Senior', 'Mid-Senior'))
def save(fig, name): fig.tight_layout(); fig.savefig(f'{OUT}/{name}.svg'); plt.close(fig)
def label(m): return m['model']
def hbars(ax, labels, values, color):
    y = np.arange(len(labels))
    ax.barh(y, values, height=0.62, color=color, edgecolor='none')
    ax.set_yticks(y, labels); ax.invert_yaxis(); ax.grid(axis='y', visible=False)
    ax.spines['left'].set_visible(False)
    for i, v in enumerate(values): ax.text(v, i, f'  {v:.0f}%', va='center', color=INK, fontsize=9.5, fontweight='semibold')
    ax.set_xlim(0, max(values) * 1.18 if len(values) else 1); ax.set_xlabel('% of catalog')
def turn_hist(tm, name):
    hi = max(300, int(np.ceil(max(tm) / 100.0) * 100)); bins = np.arange(0, hi + 100, 100)
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.axvspan(200, hi + 100, color=RED_WASH, zorder=0, lw=0)
    w = np.ones(len(tm)) * 100.0 / len(tm)
    ax.hist(tm, bins=bins, weights=w, color=INK, edgecolor=PAPER, linewidth=1.2, zorder=2)
    ax.grid(axis='x', visible=False)
    top = ax.get_ylim()[1]
    ax.axvline(200, color=RED, lw=1.4, zorder=3); ax.text(208, top * 0.95, 'long horizon, 200+ turns', color='#c83220', fontsize=9, va='top')
    m = sum(tm) / len(tm); ax.axvline(m, color=INK, lw=1, ls=(0, (4, 4)), alpha=0.7, zorder=3); ax.text(m + 8, top * 0.78, f'mean {m:.0f}', fontsize=9, color=INK)
    ax.set_xlim(0, hi + 100); ax.set_xlabel('Turns per run'); ax.set_ylabel('% of tasks')
    save(fig, name)
ALL = []
for slug, s in S.items():
    n = s['tasks']; ALL += s.get('turns', {}).get('task_means') or []
    # domains, share of catalog
    d = [(x['super_group'], 100 * x['tasks'] / n) for x in s['domain']]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(d) + 0.9))
    hbars(ax, [a for a, _ in d], [b for _, b in d], INK); ax.set_xlabel('% of catalog'); save(fig, f'{slug}_domain')
    # primary language and seniority
    fig, axes = plt.subplots(1, 2, figsize=(9, 0.42 * max(len(s['language'][:8]), 3) + 1.0), gridspec_kw={'width_ratios': [1.25, 0.75], 'wspace': 0.55})
    for ax, key, col in zip(axes, ['language', 'seniority'], [INK, TEAL]):
        dd = [(x['value'], 100 * x['tasks'] / n) for x in s[key][:8]]
        hbars(ax, [a for a, _ in dd], [b for _, b in dd], col); ax.set_xlabel('% of catalog')
    axes[0].set_title('Primary language', loc='left', color=MUTED, fontsize=9.5); axes[1].set_title('Seniority', loc='left', color=MUTED, fontsize=9.5)
    save(fig, f'{slug}_metadata')
    # per-task pass-rate distribution by model
    # saturated models (80%+ of tasks at 100%) are left out; boxes run easiest first: upper quartile, then median, then mean, descending
    SAT = 0.8
    keep = [m for m in s['models'] if m['tasks_graded'] >= 5 and m['tasks_100'] / m['tasks_graded'] < SAT]
    dropped = [label(m) for m in s['models'] if m['tasks_graded'] >= 5 and m['tasks_100'] / m['tasks_graded'] >= SAT]
    if dropped: print(slug, 'saturated, not plotted:', ', '.join(dropped))
    rk = lambda m: tuple(-x for x in (np.percentile(m['per_task_rates'], 75), np.median(m['per_task_rates']), np.mean(m['per_task_rates'])))
    keep.sort(key=rk)
    rows = [{'Model': label(m), 'r': 100 * v} for m in keep for v in m['per_task_rates']]
    if rows:
        df = pd.DataFrame(rows); k = df['Model'].nunique(); order = [label(m) for m in keep]
        fig, ax = plt.subplots(figsize=(8, 0.72 * k + 1.1))
        ax.axvspan(20, 80, color=TEAL_WASH, zorder=0, lw=0)
        sns.boxplot(df, y='Model', x='r', order=order, color=CARD, linecolor=INK, linewidth=1, fliersize=0, width=0.5, ax=ax)
        sns.stripplot(df, y='Model', x='r', order=order, color=RED, alpha=0.35, size=3, jitter=0.2, ax=ax)
        ax.grid(axis='y', visible=False); ax.spines['left'].set_visible(False)
        ax.set_xlim(-3, 103); ax.set_ylabel(''); ax.set_xlabel('Per-task pass rate (%), shaded band 20-80%')
        save(fig, f'{slug}_per_task')
    tm = s.get('turns', {}).get('task_means') or []
    if tm: turn_hist(tm, f'{slug}_turns')
    print(slug, 'ok')
if ALL: turn_hist(ALL, 'all_turns')

# overview: estimated Gemini-hard tasks per catalog against the selection by tier, and Gemini pass rates on the selection
LAB = {'Diagnosis, Debugging, and Bug Fixing': 'Debugging', 'Infrastructure as code': 'IaC'}
cats = list(S); y = np.arange(len(cats))
fig, ax = plt.subplots(figsize=(8, 3.9)); left = np.zeros(len(cats))
for tier, col in [('Proven', INK), ('Likely', '#7fb3aa')]:
    v = np.array([S[c]['tiers'].get(tier, 0) for c in cats])
    ax.barh(y, v, left=left, height=0.5, color=col, edgecolor='none', label=f'Selected: {tier.lower()}'); left += v
est = np.array([S[c]['estimate']['estimate'] for c in cats]); lo = np.array([S[c]['estimate']['lo'] for c in cats]); hi = np.array([S[c]['estimate']['hi'] for c in cats])
ax.errorbar(est, y - 0.36, xerr=[est - lo, hi - est], fmt='D', color=RED, ms=5, capsize=3, lw=1.1, label='Estimated in full catalog (95% interval)')
ax.set_yticks(y, [LAB.get(S[c]['title'], S[c]['name']) for c in cats]); ax.invert_yaxis(); ax.grid(axis='y', visible=False); ax.spines['left'].set_visible(False)
ax.set_xlabel('Tasks where Gemini 4 Argon passes under 80%'); ax.legend(frameon=False, fontsize=8.5, loc='lower right'); save(fig, 'overview_estimate')
fig, ax = plt.subplots(figsize=(8, 3.9)); h = 0.36
names = ['google/gemini-4-argon', 'google/gemini-3.8-flash']
for k, (nm, col) in enumerate(zip(names, [INK, '#7fb3aa'])):
    for i, c in enumerate(cats):
        m = next((m for m in S[c]['models'] if m['model'] == nm and m['graded']), None); yy = i + (k - 0.5) * h
        if not m: ax.text(1, yy, 'not run', va='center', fontsize=8, color=MUTED); continue
        ax.barh(yy, 100 * m['pass_rate'], height=h, color=col, label=nm if nm not in ax.get_legend_handles_labels()[1] else None)
        ax.text(100 * m['pass_rate'] + 1, yy, f"{100 * m['pass_rate']:.0f}%", va='center', fontsize=8.5, color=INK)
ax.set_yticks(y, [LAB.get(S[c]['title'], S[c]['name']) for c in cats]); ax.invert_yaxis(); ax.set_xlim(0, 100)
ax.grid(axis='y', visible=False); ax.spines['left'].set_visible(False); ax.set_xlabel('Pass rate (%)')
ax.legend(frameon=False, fontsize=8.5, loc='lower right'); save(fig, 'overview_gemini')
