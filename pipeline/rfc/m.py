import json
G,P='Go','Python'
L='Library / Backend Engineer';B='Backend Engineer';S='Security Engineer';SY='Systems Engineer';DT='Developer Tools Engineer';PL='Platform Engineer';DB='Database Engineer';CL='Compiler / Language Engineer';DE='Data Engineer';ML='ML / AI Engineer';M='Media Software Engineer';F='Frontend Engineer'
T=lambda *a:a
rows={
0:(45,G,L,0),1:(45,G,L,0),2:(1,P,ML,1),3:(1,P,ML,1),4:(47,G,M,0),5:(47,G,M,0),6:(47,G,M,0),
7:(18,G,CL,0),8:(18,G,CL,0),9:(26,G,DT,0),10:(41,G,S,0),11:(41,G,S,1),12:(25,G,L,1),13:(45,G,L,0),14:(45,G,L,0),
15:(27,G,L,0),16:(27,G,L,1),17:(27,G,L,0),18:(16,G,DB,1),19:(26,G,DT,0),20:(26,G,DT,0),21:(1,G,L,0),22:(1,G,L,1),
23:(34,G,S,0),24:(34,G,S,0),25:(34,G,S,0),26:(26,G,DT,0),27:(26,G,DT,0),28:(26,G,DT,0),
29:(48,G,F,0),30:(48,G,F,1),31:(48,G,F,0),32:(41,G,SY,1),33:(29,G,PL,0),34:(29,G,PL,0),35:(29,G,PL,0),
36:(15,G,L,1),37:(15,G,L,1),38:(15,G,L,0),39:(28,G,SY,1),40:(28,G,SY,0),41:(6,G,L,0),42:(6,G,L,1),
43:(45,G,L,0),44:(11,G,L,0),45:(45,G,L,0),46:(41,G,B,0),47:(41,G,SY,0),48:(41,G,SY,0),49:(41,G,SY,1),
50:(18,G,DT,0),51:(16,G,DB,0),52:(16,G,DB,0),53:(9,G,DE,0),54:(9,G,DE,1),55:(9,G,DE,1),
56:(41,G,SY,0),57:(41,G,SY,0),58:(41,G,SY,0),59:(18,G,CL,0),60:(18,G,CL,0),
61:(43,G,B,1),62:(43,G,B,1),63:(43,G,B,1),64:(18,G,CL,0),65:(18,G,CL,0),66:(18,G,CL,0),
67:(2,G,ML,0),68:(2,G,ML,0),69:(1,G,B,1),70:(1,P,L,0),71:(1,P,L,0),72:(33,P,S,0),
73:(17,G,L,0),74:(33,G,S,0),75:(17,G,L,0),76:(26,G,SY,0),77:(26,G,SY,0),78:(26,G,SY,0),
79:(33,G,S,1),80:(33,G,S,0),81:(33,G,S,1),82:(41,G,L,0),83:(41,G,L,0),84:(41,G,L,0),
85:(45,G,B,0),86:(45,G,B,0),87:(45,G,B,0),88:(25,G,L,0),89:(25,G,L,0),90:(25,P,L,0),91:(25,P,L,0),92:(25,P,L,0),93:(25,G,L,0),
94:(41,G,SY,0),95:(26,G,S,0),96:(25,G,L,0),97:(25,G,L,0),98:(24,G,DT,0),99:(24,G,DT,0),
100:(41,G,SY,0),101:(41,G,SY,0),102:(41,G,SY,1),103:(41,P,L,0),104:(42,P,L,0),105:(42,P,L,0),
106:(33,P,S,1),107:(33,P,S,0),108:(33,P,S,0),109:(33,P,S,0),110:(47,G,M,0),111:(47,G,M,1),112:(47,G,M,1),
113:(26,P,DT,0),114:(26,P,DT,0),115:(26,P,DT,0),116:(11,G,L,0),117:(11,G,L,0),118:(26,G,DT,0),
119:(36,P,'Observability Engineer',0),120:(36,P,'Observability Engineer',1),121:(36,P,'Observability Engineer',0),122:(36,P,'Observability Engineer',0),
123:(34,G,S,0),124:(34,G,S,0),125:(34,G,S,0),126:(34,G,S,0),
127:(29,G,PL,0),128:(29,G,PL,1),129:(29,G,PL,0),
130:(25,G,L,1),131:(25,G,L,0),132:(25,G,L,0),133:(29,G,PL,1),134:(29,G,PL,0),135:(29,G,PL,0),
136:(41,G,B,1),137:(41,G,B,0),138:(41,G,B,0),139:(29,G,PL,0),140:(29,G,PL,1),141:(29,G,PL,1),142:(29,G,PL,1),143:(29,G,PL,0),
144:(36,G,'Observability Engineer',1),145:(46,G,B,1),146:(36,G,'Observability Engineer',0),147:(26,G,DT,0),148:(26,G,S,0),
149:(37,G,B,1),150:(37,G,B,1),151:(47,G,M,0),152:(47,G,M,0),153:(47,G,M,0),
154:(11,P,L,0),155:(11,P,L,0),156:(11,P,L,0),157:(11,P,L,0),158:(11,P,L,0),
159:(33,G,S,0),160:(28,G,SY,0),161:(44,P,B,0),162:(44,P,B,0),
163:(36,G,'Observability Engineer',0),164:(36,G,'Observability Engineer',0),165:(36,G,'Observability Engineer',0),166:(36,G,'Observability Engineer',0),
167:(4,P,'Research Software Engineer',0),168:(4,P,'Research Software Engineer',0),169:(2,P,ML,0),170:(2,P,ML,0),171:(2,P,ML,0),
172:(41,P,'Embedded / IoT Engineer',0),173:(2,G,ML,0),174:(2,G,ML,1),175:(2,G,ML,0),
176:(47,G,M,0),177:(47,G,M,0),178:(47,G,M,0),179:(41,P,SY,0),180:(41,P,SY,0),181:(41,P,SY,0),
182:(33,G,B,0),183:(36,G,DT,0),184:(23,G,'Build & Release Engineer',1),185:(23,G,'Build & Release Engineer',0),186:(27,P,PL,0),
187:(11,G,L,0),188:(11,G,L,1),189:(11,G,L,0),190:(9,G,DE,0),191:(16,G,B,1),
192:(42,G,'Embedded / IoT Engineer',0),193:(42,G,'Embedded / IoT Engineer',0),194:(42,G,'Embedded / IoT Engineer',0),
195:(37,G,B,1),196:(37,G,B,1),197:(50,G,B,0),198:(50,G,B,0),199:(50,G,B,0),
200:(6,G,L,0),201:(6,G,L,0),202:(6,G,L,0),203:(16,P,L,0),204:(16,P,L,0),205:(16,P,DB,0),
206:(45,G,B,1),207:(41,G,SY,0),208:(41,G,SY,1),209:(1,P,ML,0),210:(1,P,ML,0),211:(1,P,ML,0),
212:(11,G,DE,0),213:(11,G,DE,0),214:(11,G,DE,1),215:(47,G,M,0),216:(47,G,M,0),217:(26,G,DT,0),218:(26,G,DT,0),
219:(39,P,L,0),220:(39,P,L,0),221:(39,P,L,0),222:(45,G,B,0),223:(18,G,CL,0),224:(18,G,CL,0),225:(18,G,CL,0),
226:(26,P,DT,0),227:(26,P,DT,0),228:(26,P,DT,0),229:(26,G,DT,0),230:(26,G,DT,0),231:(26,G,DT,0),
232:(50,P,B,0),233:(26,G,DT,0),234:(26,G,DT,0),235:(26,G,DT,0),236:(41,G,SY,0),237:(41,G,SY,0),
238:(4,P,'Research Software Engineer',0),239:(4,P,'Research Software Engineer',0),240:(42,P,L,0),241:(42,P,L,0),
242:(18,P,CL,0),243:(18,P,CL,0),244:(36,P,DT,0),245:(26,G,DT,0),246:(26,G,DT,0),247:(22,P,'Build & Release Engineer',0),248:(22,P,'Build & Release Engineer',0),
249:(41,P,B,0),250:(41,P,B,0),251:(41,P,B,0),252:(41,P,B,1),253:(18,P,CL,0),254:(18,P,CL,0)}
lines=open('chunks/chunk02.jsonl').read().splitlines()
assert len(lines)==len(rows)==255
out=[]
for i,l in enumerate(lines):
    d=json.loads(l);c,la,r,du=rows[i]
    out.append(json.dumps({"id":d['id'],"cat":c,"new_cat":"","lang":la,"role":r,"durable":bool(du)}))
open('out/chunk02.jsonl','w').write('\n'.join(out)+'\n')
