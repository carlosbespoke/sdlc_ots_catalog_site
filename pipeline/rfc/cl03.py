import json
L=[json.loads(l) for l in open('chunks/chunk03.jsonl') if l.strip()]
C={}
def s(a,b,c):
    for i in range(a,b+1): C[i]=c
for a,b,c in [(0,0,43),(1,3,18),(4,6,2),(7,7,29),(8,10,29),(11,11,41),(12,14,16),(15,15,25),(16,17,26),(18,22,26),(23,25,18),(26,26,50),(27,28,2),(29,32,37),(33,34,41),(35,37,1),(38,38,25),(39,40,18),(41,43,33),(44,44,1),(45,47,29),(48,49,36),(50,51,42),(52,53,17),(54,55,45),(56,56,5),(57,60,47),(61,62,44),(63,65,1),(66,66,45),(67,68,2),(69,72,1),(73,74,1),(75,77,40),(78,80,16),(81,81,2),(82,84,17),(85,85,29),(86,87,29),(88,89,37),(90,90,26),(91,92,25),(93,94,1),(95,96,2),(97,99,18),(100,102,38),(103,103,36),(104,106,42),(107,108,16),(109,111,10)]: s(a,b,c)
N={'agentscope':1,'aiogram':45,'atlantis':23,'caddy-l4':41,'casbin':33,'code-generator':29,'coroot':36,'coveragepy':26,'dasel':11,'dtls':34,'elasticsearch_exporter':36,'fantasy':1,'filebrowser':45,'fx':26,'fzf':26,'gauge':26,'gh-dash':26,'gitleaks':35,'gocron':38,'goss':27,'gqlgen':25,'import-linter':26,'isort':26,'jd':11,'jjui':26,'kafka-python':37,'keploy':25,'kool':29,'kubernetes-ingress':41,'leafwiki':46,'lefthook':26,'lipgloss':48,'litestream':16,'mangle':19,'marmot':9,'matcha':26,'micromdm':45,'model-runner':2,'mp4ff':47,'mypy_boto3_builder':25,'nanobot':1,'napalm':41,'nezha':36,'oras':29,'ormar':16,'pendulum':39,'pyscn':26,'python-polylith':22,'python-prompt-toolkit':26,'quant-mind':1,'quic-go':41,'rain':41,'revive':26,'scriggo':18,'semble':1,'sh':18,'shell-operator':29,'streamlink':47,'tablib':11,'termdash':48,'terragrunt':27,'typeagent-py':1,'umoci':29,'validator':10,'waveterm':26,'webdav':41,'werkzeug':45,'wings':29,'zha-device-handlers':42,'acme-dns':41,'afero':28,'agentcookie':26,'agentic-context-engine':1,'agentops':36,'answer':45,'argo-events':30,'ariadne':25,'autoresearchclaw':1,'aws-iam-authenticator':33,'azqr':32,'bdwgc':20,'bubbles':48,'buffalo':45,'bumble':41,'calcurse':39,'capstone':21,'chamber':33,'circumflex':26,'cli':26,'cliamp':47,'cloudflare-ddns':41,'cobra':26,'controller-tools':29,'coturn':41,'cyclopts':26,'dcmtk':3,'ddns-updater':41,'devtui':26,'dhcp':41,'discrawl':9,'django-extensions':45,'django-machina':45,'double-entry-generator':44,'dry':29,'dvc':2,'espeak-ng':47,'faker':26,'falcon':45,'fastfetch':26,'feishu-cli':26,'ffuf':41,'flask':45,'go-app':48,'go-critic':26,'go-dockerclient':29}
NEW={'dragonfly':'Game engines & servers','nano':'Game engines & servers','canopy':'Blockchain nodes','collections-c':'Data structures libraries'}
GO=set(range(7,15))|{15,16,17,26,29,30,31,32,33,34,39,40,41,42,43,45,46,47,48,49,52,53,61,62,81,82,83,84,85,86,87,88,89,90,93,94,97,98,99,100,101,102,103,107,108,109,110,111,23,24,25}
ROLE={1:'ML / AI Engineer',2:'ML / AI Engineer',3:'Research Software Engineer',4:'Research Software Engineer',5:'Data Scientist',9:'Data Engineer',10:'Library / Backend Engineer',16:'Database Engineer',17:'Database Engineer',18:'Compiler / Language Engineer',19:'Compiler / Language Engineer',20:'Systems Engineer',21:'Security Engineer',22:'Build & Release Engineer',23:'Build & Release Engineer',26:'Developer Tools Engineer',27:'Platform Engineer',28:'Systems Engineer',29:'Platform Engineer',30:'Platform Engineer',32:'Cloud Security Engineer',33:'Security Engineer',34:'Security Engineer',35:'Security Engineer',36:'Observability Engineer',37:'Backend Engineer',38:'Backend Engineer',41:'Systems Engineer',42:'Embedded / IoT Engineer',43:'Backend Engineer',44:'Backend Engineer',45:'Full-stack Engineer',47:'Media Software Engineer',48:'Frontend Engineer',50:'Backend Engineer',0:'Game Developer'}
DUR={13,14,27,33,37,42,46,47,65,72,76,77,83,87,88,91,92,93,94,104,105,145,2+0*1}
DUR.discard(2)
out=[]
for i,d in enumerate(L):
    nm=d['name']; ext=d['ext']; cat=C.get(i); new=''
    if i<112:
        lang='Go' if i in GO else 'Python'
        if i==104: lang='Python'
    else:
        base=nm.rsplit('-blind',1)[0].rsplit('-misled',1)[0].rsplit('-',1)[0]
        if base in NEW: new=NEW[base]; cat=0
        else: cat=N[base]
        lang='Go' if 'Go' in ext else 'C' if 'C' in ext else 'Python'
    role=ROLE.get(cat,'Library / Backend Engineer')
    if cat==0: role='Game Developer' if 'Game' in new else 'Systems Engineer' if 'Block' in new else 'Library / Backend Engineer'
    if cat==31 : role='Platform Engineer'
    dur = (i in DUR) if i<112 else (nm.startswith('litestream'))
    out.append(dict(id=d['id'],cat=cat,new_cat=new,lang=lang,role=role,durable=dur))
open('out/chunk03.jsonl','w').write(''.join(json.dumps(o)+'\n' for o in out))
print(len(out),sum(o['cat']==0 for o in out),{o['new_cat'] for o in out})
