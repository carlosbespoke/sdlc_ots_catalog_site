import json,re
T='Text & markup processing'; F='Fonts & text rendering'; G='Code formatters & linters'
DT='Developer Tools Engineer';LB='Library / Backend Engineer';CL='Compiler / Language Engineer';MS='Media Software Engineer';RS='Research Software Engineer';SY='Systems Engineer'
# idx: (cat,new,role)
M={}
def s(i,c,r,n=''): M[i]=(c,n,r)
s(0,0,DT,T);s(1,18,CL);s(2,25,DT);s(3,26,DT);s(4,26,DT);s(5,18,CL);s(6,18,CL);s(7,26,DT);s(8,0,SY,'System information libraries');s(9,47,MS)
s(10,24,DT);s(11,25,DT);s(12,18,CL);s(13,18,CL);s(14,29,'Platform Engineer');s(15,0,RS,'Data visualization');s(16,26,DT);s(17,26,DT);s(18,18,CL);s(19,22,'Build & Release Engineer')
s(20,22,'Build & Release Engineer');s(21,47,MS);s(22,18,CL);s(23,18,CL);s(24,26,DT);s(25,47,MS);s(26,10,DT);s(27,22,'Build & Release Engineer');s(28,26,DT);s(29,15,LB)
s(30,13,LB);s(31,0,'Embedded / IoT Engineer','Emulators');s(32,0,LB,T);s(33,0,LB,T);s(34,21,SY);s(35,27,'Platform Engineer');s(36,26,DT);s(37,22,DT);s(38,4,RS);s(39,26,DT)
s(40,18,CL);s(41,16,'Database Engineer');s(42,0,LB,T);s(43,26,DT);s(44,25,DT);s(45,18,CL);s(46,47,MS);s(47,47,MS);s(48,26,DT);s(49,25,DT)
s(50,28,SY);s(51,29,'Platform Engineer');s(52,26,DT);s(53,0,LB,T);s(54,0,LB,T);s(55,29,'Platform Engineer');s(56,26,DT);s(57,47,MS);s(58,0,LB,T);s(59,18,CL)
s(60,13,LB);s(61,44,'Backend Engineer');s(62,18,CL);s(63,18,CL);s(64,18,CL);s(65,42,'Embedded / IoT Engineer');s(66,47,MS);s(67,10,DT);s(68,18,CL);s(69,13,LB)
s(70,25,DT);s(71,11,LB);s(72,25,DT);s(73,28,SY);s(74,19,CL);s(75,47,MS);s(76,26,DT);s(77,18,CL);s(78,18,CL);s(79,0,'Game Developer','Game engines')
s(80,4,RS);s(81,18,CL);s(82,18,CL);s(83,47,MS);s(84,2,'ML / AI Engineer');s(85,0,'Game Developer','Game engines');s(86,11,LB);s(87,47,MS);s(88,26,DT);s(89,11,LB)
s(90,47,MS);s(91,47,MS);s(92,26,DT);s(93,26,DT);s(94,25,DT);s(95,26,DT);s(96,18,CL);s(97,18,CL);s(98,18,CL);s(99,18,CL)
s(100,0,LB,T);s(101,35,'Security Engineer');s(102,18,CL);s(103,42,'Embedded / IoT Engineer');s(104,11,LB);s(105,13,LB);s(106,18,CL);s(107,47,MS);s(108,47,MS);s(109,26,DT)
s(110,25,DT);s(111,24,'Build & Release Engineer');s(112,23,DT);s(113,0,LB,T);s(114,2,'ML / AI Engineer');s(115,25,DT);s(116,26,DT);s(117,25,DT);s(118,26,DT);s(119,0,LB,F)
s(120,0,LB,T);s(121,13,LB);s(122,24,DT);s(123,27,'Platform Engineer');s(124,18,CL);s(125,25,DT);s(126,18,CL);s(127,47,MS);s(128,0,LB,T);s(129,0,LB,T)
s(130,13,LB);s(131,47,MS);s(132,18,CL);s(133,13,LB);s(134,0,RS,'CAD & BIM');s(135,29,'Platform Engineer');s(136,4,RS);s(137,12,'Security Engineer');s(138,26,DT);s(139,18,CL)
s(140,47,MS);s(141,26,DT);s(142,17,'Database Engineer');s(143,0,LB,T);s(144,17,'Database Engineer');s(145,19,CL);s(146,25,DT);s(147,18,CL);s(148,0,LB,T);s(149,26,DT)
s(150,26,DT);s(151,18,CL);s(152,4,RS);s(153,25,DT);s(154,15,RS);s(155,0,LB,T);s(156,18,CL);s(157,26,DT);s(158,26,DT);s(159,0,LB,F)
s(160,18,CL);s(161,13,LB);s(162,0,LB,T);s(163,26,DT);s(164,0,LB,T);s(165,0,LB,F);s(166,18,CL);s(167,0,LB,T);s(168,4,RS);s(169,26,DT)
s(170,27,'Platform Engineer');s(171,0,LB,'Data visualization');s(172,4,RS);s(173,4,RS);s(174,4,RS);s(175,6,RS);s(176,6,RS);s(177,13,LB);s(178,47,MS);s(179,11,LB)
s(180,13,RS);s(181,47,MS);s(182,26,DT);s(183,18,CL);s(184,13,LB);s(185,6,RS);s(186,15,RS);s(187,18,CL);s(188,4,RS);s(189,4,RS)
s(190,23,DT);s(191,26,DT);s(192,18,CL);s(193,11,LB);s(194,18,CL);s(195,18,CL);s(196,11,DT);s(197,26,DT);s(198,26,DT);s(199,11,DT)
s(200,18,CL);s(201,26,DT);s(202,0,LB,T);s(203,44,'Backend Engineer');s(204,18,CL);s(205,47,MS);s(206,4,RS);s(207,18,CL);s(208,18,CL);s(209,13,LB)
s(210,18,CL);s(211,0,LB,T);s(212,18,CL);s(213,27,CL);s(214,22,'Build & Release Engineer');s(215,0,LB,'Other');s(216,17,'Database Engineer');s(217,24,'Security Engineer');s(218,0,LB,F);s(219,25,DT)
s(220,39,LB);s(221,33,'Security Engineer');s(222,25,DT);s(223,29,'Platform Engineer');s(224,4,RS);s(225,0,LB,T);s(226,26,DT);s(227,0,LB,T);s(228,18,CL);s(229,0,'Frontend Engineer',G)
s(230,13,LB);s(231,18,CL);s(232,0,RS,'CAD & CAM');s(233,26,DT);s(234,24,'Security Engineer');s(235,18,CL);s(236,4,RS);s(237,21,'Security Engineer');s(238,21,'Security Engineer');s(239,48,'Frontend Engineer')
s(240,13,LB);s(241,18,CL);s(242,22,'Build & Release Engineer');s(243,18,CL);s(244,29,'Platform Engineer');s(245,0,LB,T);s(246,18,CL);s(247,26,DT);s(248,18,CL);s(249,26,DT)
s(250,4,RS);s(251,26,DT);s(252,4,RS);s(253,16,'Database Engineer');s(254,17,'Database Engineer')
for i in range(255):
    if i in M and M[i][0]==0: pass
M[215]=(34,'','Security Engineer')  # mithril? placeholder
M[213]=(18,'',CL)
M[8]=(0,'System information libraries',SY)
M[229]=(0,'Code formatters & linters','Frontend Engineer')
# fix a few
M[0]=(26,'',DT);M[32]=(0,T,LB);M[171]=(0,'Data visualization',LB);M[15]=(0,'Data visualization',RS)
M[22]=(18,'',CL);M[92]=(0,G,DT);M[93]=(0,G,DT);M[109]=(0,G,DT);M[149]=(0,G,DT);M[157]=(0,G,DT);M[67]=(0,G,DT);M[135]=(0,G,DT);M[225]=(0,T,LB)
M[215]=(0,'Other',LB)
M[215]=(41,'','Security Engineer')
M[28]=(26,'',DT)
rows=[json.loads(l) for l in open('chunks/chunk09.jsonl')]
out=[]
for i,d in enumerate(rows):
    m=re.search(r'existing (\w[\w+#]*) implementation',d['instr'])
    lang=m.group(1) if m else 'Go'
    if i==28: lang='Go'
    c,n,r=M[i]
    out.append(json.dumps({"id":d['id'],"cat":c,"new_cat":n if c==0 else "","lang":lang,"role":r,"durable":False}))
open('out/chunk09.jsonl','w').write('\n'.join(out)+'\n')
from collections import Counter
print(len(out),sum(1 for i in M.values() if i[0]==0),Counter(v[1] for v in M.values() if v[0]==0),Counter(json.loads(o)['lang'] for o in out))
