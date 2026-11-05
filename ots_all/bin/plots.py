# Plots for the all-models catalogs: domains, language and seniority, per-task pass rate by model, turn counts, and the overview's pass rate by model and catalog.
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
    keep = [m for m in s['models'] if m['tasks_graded'] >= s['min_tasks'] and m['tasks_100'] / m['tasks_graded'] < SAT]
    dropped = [label(m) for m in s['models'] if m['tasks_graded'] >= s['min_tasks'] and m['tasks_100'] / m['tasks_graded'] >= SAT]
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

# overview: pass rate of each model in each catalog, for models with graded runs on 5 or more tasks there (blank otherwise)
LAB = {'Diagnosis, Debugging, and Bug Fixing': 'Debugging', 'Infrastructure as code': 'IaC', 'Feature implementation': 'Feature impl.'}
cats = list(S); MIN = S[cats[0]]['min_tasks']
tot = {}
for c in cats:
    for m in S[c]['models']: tot[m['model']] = tot.get(m['model'], 0) + m['rollouts']
models = [m for m in sorted(tot, key=lambda m: -tot[m]) if any(x['model'] == m and x['tasks_graded'] >= MIN for c in cats for x in S[c]['models'])]
grid = np.full((len(models), len(cats)), np.nan); ntask = np.zeros((len(models), len(cats)), int)
for j, c in enumerate(cats):
    for x in S[c]['models']:
        if x['model'] in models and x['tasks_graded'] >= MIN:
            grid[models.index(x['model']), j] = 100 * x['pass_rate']; ntask[models.index(x['model']), j] = x['tasks_graded']
cell = lambda v: '<1%' if 0 < v < 0.5 else f'{v:.0f}%'  # same rounding as the tables
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list('b', ['#fbf9f4', '#7fb3aa', INK])
fig, ax = plt.subplots(figsize=(9.5, 0.62 * len(models) + 1.6))
ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, vmin=0, vmax=100, aspect='auto')
for i in range(len(models)):
    for j in range(len(cats)):
        v = grid[i, j]
        if not np.isnan(v):
            col = 'white' if v > 55 else INK
            ax.text(j, i - 0.1, cell(v), ha='center', va='center', fontsize=9, fontweight='semibold', color=col)
            ax.text(j, i + 0.24, f'{ntask[i, j]} tasks', ha='center', va='center', fontsize=6.5, color=col)
ax.set_xticks(range(len(cats)), [LAB.get(S[c]['title'], S[c]['title']) for c in cats], rotation=20, ha='right'); ax.set_yticks(range(len(models)), models)
ax.grid(False); [sp.set_visible(False) for sp in ax.spines.values()]
ax.set_xticks(np.arange(-.5, len(cats)), minor=True); ax.set_yticks(np.arange(-.5, len(models)), minor=True)
ax.grid(which='minor', color=PAPER, linewidth=2); ax.tick_params(which='minor', length=0)
save(fig, 'overview_models')
