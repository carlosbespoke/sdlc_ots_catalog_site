import json,re
L=[json.loads(l) for l in open('chunks/chunk04.jsonl')]
R={'LB':'Library / Backend Engineer','BE':'Backend Engineer','DT':'Developer Tools Engineer','CL':'Compiler / Language Engineer','SE':'Systems Engineer','SEC':'Security Engineer','CS':'Cloud Security Engineer','PL':'Platform Engineer','OB':'Observability Engineer','SRE':'SRE','MS':'Media Software Engineer','GD':'Game Developer','DB':'Database Engineer','DE':'Data Engineer','ML':'ML / AI Engineer','RS':'Research Software Engineer','FS':'Full-stack Engineer','FE':'Frontend Engineer','EM':'Embedded / IoT Engineer','BR':'Build & Release Engineer','HW':'Hardware Engineer','GPU':'GPU / Performance Engineer'}
M={}
def s(i,c,r,d=False,n=''): M[i]=(c,r,d,n)
a=[(0,41,'LB'),(1,41,'LB'),(2,25,'LB'),(3,33,'LB'),(4,25,'LB'),(5,41,'SE'),(6,38,'LB'),(7,18,'CL'),(8,1,'BE'),(9,12,'SEC'),(10,26,'SRE'),(11,18,'CL'),(12,25,'LB'),(13,6,'RS'),(14,22,'BR'),(15,25,'LB'),(16,26,'DT'),(17,41,'BE'),(18,29,'PL'),(19,41,'SE'),(20,13,'SE'),(21,26,'DT'),(22,11,'DT'),(23,26,'DT'),(25,29,'PL'),(26,37,'LB'),(27,25,'DT'),(28,36,'LB'),(29,29,'DT'),(30,32,'CS'),(31,32,'CS'),(32,29,'PL'),(33,45,'FS'),(34,26,'DT'),(35,11,'LB'),(36,13,'SE'),(37,12,'SE'),(38,12,'SE'),(39,34,'SEC'),(40,34,'SEC'),(41,41,'SE'),(42,29,'PL'),(43,25,'LB'),(44,48,'DT'),(46,19,'CL'),(48,26,'DT'),(49,1,'SEC'),(50,5,'RS'),(51,29,'PL'),(53,45,'BE'),(54,45,'BE'),(55,25,'LB'),(56,2,'ML'),(57,47,'MS'),(58,50,'DT'),(59,25,'DT'),(60,36,'OB'),(61,41,'BE'),(62,1,'ML'),(63,37,'SE'),(64,41,'SE'),(65,41,'SE'),(66,32,'SEC'),(67,36,'SRE'),(68,5,'RS'),(69,25,'LB'),(70,33,'LB'),(71,33,'LB'),(72,27,'PL'),(73,33,'SEC'),(74,47,'MS'),(75,24,'PL'),(76,16,'LB'),(77,24,'BR'),(78,41,'BE'),(79,45,'FS'),(80,39,'LB'),(81,17,'DT'),(82,9,'DE'),(83,18,'CL'),(84,50,'BE'),(85,25,'DT'),(86,27,'PL'),(87,18,'DT'),(88,22,'DT'),(89,26,'DT'),(90,26,'DT'),(91,26,'DT'),(92,1,'ML'),(93,1,'ML'),(94,31,'PL'),(95,36,'SRE'),(96,26,'DT'),(98,29,'PL'),(99,36,'OB'),(100,34,'SEC'),(102,18,'CL'),(103,1,'ML'),(104,1,'ML'),(105,18,'CL'),(106,41,'SE'),(107,29,'PL'),(108,33,'SEC'),(109,25,'LB'),(110,32,'SEC'),(111,1,'ML'),(112,36,'SE'),(113,36,'OB'),(114,42,'EM'),(115,45,'BE'),(116,5,'RS'),(117,47,'MS'),(118,1,'PL'),(119,11,'LB'),(120,35,'SEC'),(121,25,'LB'),(122,48,'DT'),(123,27,'PL'),(124,32,'SEC'),(125,1,'ML'),(126,1,'ML'),(127,24,'PL'),(129,36,'OB'),(130,50,'SEC'),(131,45,'BE'),(132,10,'LB'),(133,26,'DT'),(134,26,'DT'),(135,41,'BE'),(136,45,'BE'),(137,45,'BE'),(138,41,'SE'),(139,29,'PL'),(140,41,'LB'),(141,13,'SE'),(142,18,'CL'),(143,11,'DT'),(144,36,'LB'),(145,42,'EM'),(146,13,'SE'),(147,36,'LB'),(148,10,'LB'),(149,45,'BE'),(150,4,'RS'),(151,41,'LB'),(152,41,'LB'),(153,41,'LB'),(154,5,'RS'),(155,2,'ML'),(156,2,'ML'),(157,2,'ML'),(158,2,'ML'),(159,5,'RS'),(160,5,'RS'),
(161,26,'DT'),(162,12,'SEC'),(163,18,'CL'),(164,18,'DT'),(165,18,'CL'),(166,18,'CL'),(167,47,'MS'),(168,18,'CL'),(169,47,'MS'),(170,11,'DT'),(171,26,'DT'),(172,26,'DT'),(173,18,'DT'),(174,18,'DT'),(175,26,'DT'),(176,26,'DT'),(177,18,'CL'),(178,17,'DT'),(179,18,'CL'),(180,18,'CL'),(181,26,'DT'),(182,4,'SE'),(183,47,'MS'),(184,26,'DT'),(185,25,'DT'),(186,18,'CL'),(187,18,'CL'),(188,6,'RS'),(189,29,'PL'),(190,47,'MS'),(191,18,'DT'),(192,26,'DT'),(193,26,'DT'),(194,18,'DT'),(195,22,'BR'),(196,22,'BR'),(197,47,'MS'),(198,18,'CL'),(199,18,'CL'),(200,26,'DT'),(201,47,'MS'),(202,10,'DT'),(203,22,'BR'),(204,26,'DT'),(205,18,'LB'),(206,13,'LB'),(208,26,'LB'),(209,11,'LB'),(210,21,'LB'),(211,27,'PL'),(212,26,'DT'),(213,22,'DT'),(214,4,'RS'),(215,26,'DT'),(216,18,'CL'),(217,16,'DB'),(218,48,'DT'),(219,26,'DT'),(220,18,'DT'),(221,18,'DT'),(222,47,'MS'),(223,47,'MS'),(224,26,'DT'),(225,25,'DT'),(226,47,'MS'),(227,28,'SE'),(228,29,'PL'),(229,26,'DT'),(230,47,'DT'),(231,18,'DT'),(232,26,'PL'),(233,52,'HW'),(234,26,'DT'),(235,47,'MS'),(236,45,'DT'),(237,18,'CL'),(238,47,'MS'),(239,44,'DE'),(240,18,'CL'),(241,18,'CL'),(242,18,'CL'),(243,42,'EM'),(244,47,'MS'),(245,26,'DT'),(246,26,'DT'),(247,18,'CL'),(248,13,'LB'),(249,18,'CL'),(250,11,'LB'),(251,25,'DT'),(252,13,'SE'),(253,19,'CL'),(254,41,'SE')]
for i,c,r in a: s(i,c,r)
s(24,0,'GD',n='Game engines'); s(52,0,'SE',n='Emulators'); s(128,0,'SE',n='Emulators'); s(101,0,'DT',n='Spreadsheets')
s(97,16,'LB'); s(45,16,'DB',True); s(47,16,'DB',True)
s(207,0,'EM',n='Emulators'); s(6,38,'LB',True)
s(210,21,'LB')
out=open('out/chunk04.jsonl','w')
for i,d in enumerate(L):
    c,r,du,n=M[i]; nm=d['name']; ins=d['instr']
    m=re.search(r'existing (C\+\+|C#|\w+) impl',ins)
    if m: lang=m.group(1)
    else:
        e=d['ext']; df=str(d['docker_from']).lower()
        lang=max((k for k in e if k!='Python' or len(e)==1),key=e.get,default='Python') if len(e)>0 else 'Python'
        if i in (149,): lang='Python'
        if i in (150,154,155,156,157,158,159,160): lang='Python'
        if i in (151,152,153): lang='Go'
        if i==241: lang='Rust'
        if i in (37,38): lang='C'
        if i==8: lang='Python'
    if lang=='TypeScript' and False: pass
    out.write(json.dumps({'id':d['id'],'cat':c,'new_cat':n,'lang':lang,'role':R[r],'durable':du})+'\n')
