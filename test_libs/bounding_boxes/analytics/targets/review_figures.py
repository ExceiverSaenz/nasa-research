"""Visual reference plates with ROI outline and no tool/category labels."""

import sys
from pathlib import Path
_BBX_ROOT = next(p for p in Path(__file__).resolve().parents if (p/'.layout.json').is_file())
sys.path.insert(0, str(_BBX_ROOT))
sys.path.insert(0, str(_BBX_ROOT/'code'))
from bbx.layout import project_root, resolve_path
import sys
from pathlib import Path
from analytics.targets.prepare import OUT,BASE,readlines,sha,jsonout
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

cases=readlines(OUT/'visual_cases.jsonl');hashes={}
for offset in range(0,len(cases),8):
    fig,axes=plt.subplots(4,2,figsize=(15,14))
    for ax,c in zip(axes.flat,cases[offset:offset+8]):
        p=BASE/'raw_results/code/mineru-nativefix-20261101T034122Z/viewer_source/pages'/c['paper_sha256']/f"{c['page_idx']}.png";hashes[str(p)]=sha(p);img=plt.imread(p);b=c['roi']
        ax.imshow(img,extent=(0,1,1,0));ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=False,edgecolor='#008cba',linewidth=1.2))
        ax.set_xlim(max(0,b[0]-.035),min(1,b[2]+.035));ax.set_ylim(min(1,b[3]+.025),max(0,b[1]-.025));ax.set_title(f"{c['case_id']} · {c['paper']} p{c['page_idx']+1}");ax.axis('off')
    for ax in list(axes.flat)[len(cases[offset:offset+8]):]:ax.axis('off')
    fig.suptitle('Referencia visual: identificar función del contenido dentro del recuadro',fontsize=13);fig.tight_layout();fig.savefig(OUT/f'review_{offset//8+1:02}.png',dpi=120);plt.close(fig)
assert all(sha(p)==h for p,h in hashes.items());jsonout(OUT/'review_figures_verification.json',dict(input_hashes=hashes,unchanged=True,code_hash=sha(__file__)))
print('Nine visual review plates generated')
