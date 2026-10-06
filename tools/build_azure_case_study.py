"""Build the public Azure case study and its downloadable PDF from local evidence."""
from pathlib import Path
import re, json, html, shutil, subprocess
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'azure-case-study-evidence'
PUBLIC = ROOT / 'azure-case-study' / 'images'
OUT = ROOT / 'output' / 'pdf'
BUILD = ROOT / 'tmp' / 'azure-case-study'
SOURCE = Path('C:/Projects/AZURE_3way_env/azure-appservice-platform-lab')
for p in [PUBLIC, OUT, BUILD]: p.mkdir(parents=True, exist_ok=True)
SHA = subprocess.check_output(['git','rev-parse','HEAD'], cwd=SOURCE, text=True).strip()
SOURCE_URL = 'https://github.com/PeterHudcovic/azure-appservice-platform-lab/blob/' + SHA + '/'

initial = {
 'prod-demo-application.png': 'The production demo application provides a browser view of the deployed application and its identity and Key Vault checks. This is application evidence, separate from infrastructure configuration.',
 'subscriptions.png': 'Development and testing share sub-app-nonprod. Production uses sub-app-prod, creating a separate subscription boundary for management access, policy and cost tracking.',
 'entra-app-user-groups.png': 'Each environment has its own application user group. These groups control application sign-in and do not grant Azure resource administration.',
 'entra-dev-app-users-members.png': 'The development app-user group lists its captured membership. Lab Admin belongs to the group for the application demonstration.',
 'entra-test-app-users-members.png': 'The testing app-user group lists its captured membership. Application membership is separate from management-plane roles.',
 'entra-prod-app-users-members.png': 'The production app-user group lists its captured membership. Protected application routes require the environment application assignment.',
}
captions = dict(initial)
raw = (EVIDENCE/'captions.txt').read_text(encoding='utf-8-sig')
matches = list(re.finditer(r'^.*?([a-zA-Z0-9-]+\.png)\s*$', raw, re.M))
for i,m in enumerate(matches):
 body = raw[m.end():matches[i+1].start() if i+1<len(matches) else len(raw)].strip()
 body = re.sub(r'^PLACEMENT:.*\n?', '', body, flags=re.M).strip()
 captions[m.group(1)] = body

# The user's publishing rules exclude connection strings. Keep this original local.
excluded = {'prod-application-insights-overview.png': 'Application Insights overview displays a connection string.'}
entries = []
for p in sorted(EVIDENCE.glob('*.png')):
 if p.name in excluded: continue
 if p.name not in captions: raise ValueError('Missing caption: '+p.name)
 title = p.stem.replace('-', ' ').capitalize()
 if p.name.startswith('entra-') or p.name.startswith('prod-pim') or p.name.startswith('prod-admin-') and 'session' not in p.name:
  group='Users and access'
 elif 'identity' in p.name or 'identities' in p.name:
  group='Managed identities'
 elif any(x in p.name for x in ['devops','managed-pool','service-connection','pipeline','approval']): group='Shared CI/CD'
 elif any(x in p.name for x in ['monitor','diagnostic','analytics','insights']): group='Monitoring'
 elif p.name=='subscriptions.png' or p.name=='prod-demo-application.png': group='Overview'
 elif p.name.startswith('dev-'): group='Development'
 elif p.name.startswith('test-'): group='Testing'
 else: group='Production networking and operations'
 with Image.open(p) as im: w,h=im.size
 entries.append(dict(file=p.name,title=title,caption=captions[p.name],group=group,width=w,height=h))
 shutil.copy2(p,PUBLIC/p.name)
# Identity overview belongs before detailed role assignments.
entries.sort(key=lambda e:(e['group'], 0 if e['file']=='managed-identities-subscription-overview.png' else 1, e['file']))

chapters = [
 dict(id='overview',title='Overview and subscriptions',text='I built a private Azure application platform in Sweden Central with separate development, testing and production environments. Dev and Test share the non-production subscription. Production has its own subscription, identities, network and Terraform state. The shared package store lives in the Dev foundation resource group.',image='subscriptions.png',source='README.md'),
 dict(id='access',title='Users and access',text='Application sign-in and infrastructure administration use separate grants. Lab Admin bootstraps the lab and belongs to the app-user groups. Prod Admin has permanent Reader and Virtual Machine User Login, with privileged resource and secret roles available through PIM. PIM activation requires justification and MFA and lasts at most two hours. Conditional Access policies evaluate non-production NAT locations and device-code sign-in in report-only mode.',image='prod-admin-subscription-reader-and-eligible-contributor.png',source='infra/environments/production/layer-0-foundation/access.tf'),
 dict(id='identities',title='Managed identities and role boundaries',text='Each environment has six user-assigned identities for the application, gateway, deploy, destroy and two infrastructure layers. Dev foundation also hosts the shared build identity. Runtime identities read secrets at their assigned scopes. Pipeline identities use workload identity federation. Contributor and Website Contributor are broader than a single operation, so I document the actual role scopes instead of treating them as strict deploy-only or delete-only permissions.',image='managed-identities-subscription-overview.png',source='docs/build-log/13-access-matrix.md'),
 dict(id='delivery',title='Shared CI/CD',text='Azure DevOps builds one Python package, runs unit tests, records the source commit and SHA-256, and uploads the package to shared storage. Deploy jobs retrieve and verify the same package through environment-specific identities and private application agent pools. YAML enables Dev and Test completion triggers for main builds. Captured lab runs were manual on the working branch. Production deployment requires approval on prod-app, with self-approval enabled in this lab.',image='azure-devops-successful-pipeline-overview.png',source='pipelines/templates/deploy-steps.yml'),
 dict(id='terraform',title='Terraform layers and infrastructure delivery',text='Layer 0 retains foundation resources and identities. Layer 1 creates networking and operations. Layer 2 creates the application platform. Every environment and layer has a separate state container with Entra authentication. Layer 1 pipelines use hosted agents because they create the private pools. Layer 2 uses the environment infrastructure pool. Production has a plan stage and an approval on prod-infra, followed by a new plan, conditional apply and verification. Build log 12 records No changes runs in all environments.',image='azure-devops-agent-pools-all-environments.png',source='docs/build-log/12-monitoring-alerts-and-infrastructure-pipelines.md'),
 dict(id='network',title='Networking and private access',text='The VNets use 10.10.0.0/16, 10.20.0.0/16 and 10.30.0.0/16 with no peering. Subnets separate operations, gateway, application integration, private endpoints and pipeline agents. Private DNS zones link to their own VNet. App Service inbound private endpoints and outbound VNet integration serve different directions of traffic. NSGs use explicit permitted flows followed by deny-all inbound at priority 4000. NAT attaches to operations, application and agent subnets.',image='prod-vnet-subnets.png',source='docs/build-log/14-acceptance-checks-and-certificate-trust.md'),
 dict(id='dev',title='Development',text='Development uses sub-app-nonprod and vnet-sits-dev-swc with address space 10.10.0.0/16. The private gateway is 10.10.4.10 and the application hostname is app.dev.sits.internal. App Service uses B1. Development hosts the shared package store and the monitoring workspace used by both non-production environments. Separate application and infrastructure pools run jobs within the Dev network.',image='dev-vnet-connected-devices.png',source='docs/build-log/07-development-network-operations.md'),
 dict(id='test',title='Testing',text='Testing uses the same non-production subscription but its own resource groups, VNet, identities and state. The VNet is 10.20.0.0/16, the gateway is 10.20.4.10 and the hostname is app.test.sits.internal. App Service uses P0v3. Testing reads the shared package and reuses the Dev Log Analytics and Application Insights resources. This is an explicit monitoring dependency rather than complete resource independence.',image='test-vnet-connected-devices.png',source='docs/build-log/10-testing-environment.md'),
 dict(id='prod',title='Production',text='Production uses sub-app-prod and 10.30.0.0/16. App Service uses P0v3 and the private gateway listens at 10.30.4.10 for app.prod.sits.internal. Production has its own monitoring, Bastion Basic, delete locks, PIM and separate approval environments. Public access is disabled on the Web App and application Key Vault. Certificate and admin foundation vaults retain public access, even though private endpoints also exist.',image='prod-app-service-networking.png',source='docs/build-log/11-production-environment.md'),
 dict(id='gateway',title='Gateway, WAF and TLS',text='The WAF_v2 gateway exposes a private HTTPS listener and forwards to the App Service hostname using HTTPS on port 443. A custom /health probe returned HTTP 200 and the backend was Healthy at capture time. Microsoft Default Rule Set 2.1 runs in Detection mode. A managed identity retrieves the listener certificate from the certificate vault. The self-signed certificate is trusted locally on each Ops VM as recorded in build log 14, and must be imported again after renewal or VM rebuild.',image='prod-application-gateway-backend-health.png',source='docs/build-log/14-acceptance-checks-and-certificate-trust.md'),
 dict(id='bastion',title='Operations access through Bastion',text='Bastion provides the operations entry point without a public IP on the VM NIC. Production supports Microsoft Entra ID sign-in through AADLoginForWindows and the permanent VM User Login grant. My captured session returned azuread\\prodadmin. The local opsadmin account remains a separate emergency administrator path. The Entra user session does not need the local VM password or an activated Contributor role.',image='prod-operations-vm-entra-login-whoami.png',source='docs/build-log/14-acceptance-checks-and-certificate-trust.md'),
 dict(id='validation',title='Runtime validation from the production VM',text='From source 10.30.1.4, app.prod.sits.internal resolved to the gateway at 10.30.4.10 and TCP port 443 was reachable. App Service resolved through privatelink.azurewebsites.net to 10.30.5.7. The application vault resolved through privatelink.vaultcore.azure.net to 10.30.5.6. These terminal outputs prove private DNS resolution and gateway TCP reachability. Build log 14 separately records trusted HTTPS /health responses and cross-environment DNS isolation tests.',image='prod-admin-session-runtime-dns-and-gateway-connectivity.png',source='docs/build-log/14-acceptance-checks-and-certificate-trust.md'),
 dict(id='application',title='Application and identity',text='The Python demo runs on Linux App Service with Entra Easy Auth. An assigned application group controls protected routes. The application managed identity reads the application vault, while a federation credential supports the sign-in configuration without an app-registration client secret. The /health route deliberately allows anonymous probing from network-authorized clients. Application access and Key Vault RBAC remain separate checks.',image='prod-demo-application.png',source='infra/environments/production/layer-2-application/appservice.tf'),
 dict(id='monitoring',title='Monitoring and diagnostics',text='Gateway allLogs and AllMetrics stream to the production Log Analytics workspace using AzureDiagnostics tables. Dev and Test share the non-production workspace. Four custom alert rules per environment cover application health, unhealthy gateway backends, denied application-vault access and WAF matches. Production also has a Failure Anomalies smart detector. The Application Insights overview had no request telemetry in its selected one-hour window, so it does not prove active application instrumentation.',image='prod-gateway-diagnostic-settings-details.png',source='infra/environments/production/layer-2-application/alerts.tf'),
 dict(id='alerts',title='Observed alerts',text='The captured Azure Monitor view lists 16 fired instances across the selected subscriptions: 13 warnings and three informational alerts. These include repeated Key Vault access-denied results and WAF matches. WAF is in Detection, so a matched request does not establish prevention-mode blocking. The alert inventory and fired instances show configuration and observed events separately.',image='azure-monitor-fired-alerts-all-environments.png',source='docs/build-log/12-monitoring-alerts-and-infrastructure-pipelines.md'),
 dict(id='next',title='Limitations and next steps',text='The current lab is deployed and demonstrated. Next work includes Terraform modules, a destroy-and-rebuild exercise, removal of temporary administrator state grants after approval, WAF Prevention after tuning, Conditional Access enforcement after report review, and a certificate from a trusted CA. Developer and tester infrastructure groups and app-user/app-denied demonstration accounts are not implemented. Foundation vault public exposure, shared monitoring dependencies and broad built-in roles remain visible design limits.',image=None,source='README.md'),
]

roles = [
 ['Account / identity','Scope and capability','Boundary'],
 ['Lab Admin','Bootstrap across all environments; app-group member','Broad administrator, no declared Entra VM login grant'],
 ['Prod Admin','Reader + VM User Login permanently; PIM Contributor and secret roles','Prod scope; privileged roles need activation'],
 ['App-user groups','Sign-in to assigned environment application','No Azure management role; /health excluded'],
 ['Application MI','Secrets User on own application-vault RG','Secret read; no secret write grant'],
 ['Gateway MI','Secrets User on certificate vault','Vault scope, not a single certificate'],
 ['Build MI','Blob Data Contributor on shared packages','Read/write/delete blobs, not upload only'],
 ['Deploy MI','Website Contributor on own app RG; package Blob Reader','Website management exceeds package deploy'],
 ['Infra L1 / L2','Contributor on own layer RGs; state and dependency grants','No role assignment; resource changes can use runtime MIs'],
 ['Destroy MI','Contributor on network/app/vault RGs and state access','Create/update/delete, not delete only'],
 ['Prod lock roles','Infra L2 creates locks; destroy removes locks','Explicit custom lock grants on app/vault RGs'],
 ['DevOpsInfrastructure','Reader + Network Contributor on network RG','Pool placement, not application data access'],
]
envtable = [
 ['','Development','Testing','Production'],
 ['Subscription','sub-app-nonprod','sub-app-nonprod','sub-app-prod'],
 ['VNet CIDR','10.10.0.0/16','10.20.0.0/16','10.30.0.0/16'],
 ['Gateway private IP','10.10.4.10','10.20.4.10','10.30.4.10'],
 ['App Service plan','B1','P0v3','P0v3'],
 ['Monitoring','Dev workspace','Shared Dev workspace','Own workspace'],
 ['Bastion SKU','Developer','Developer','Basic'],
 ['Application delivery','main completion trigger','main completion trigger','Manual approval'],
 ['Privileged access','Lab bootstrap admin','Lab bootstrap admin','Reader + VM login, PIM roles'],
]

def esc(s): return html.escape(s,quote=True)
diagram_nodes = [
 (25,30,270,95,'Shared delivery',['GitHub source and Azure DevOps','One ZIP package and SHA-256']),
 (25,165,270,115,'Dev foundation package store',['sub-app-nonprod','All deployment identities read packages']),
 (345,30,265,250,'Development and testing',['sub-app-nonprod','Dev: 10.10.0.0/16','Test: 10.20.0.0/16','Separate state, identities and VNets','Shared non-production monitoring']),
 (660,30,265,250,'Production',['sub-app-prod','Prod: 10.30.0.0/16','Own state, identities and monitoring','Application and infrastructure approvals','Reader, VM login and PIM']),
]
diagram_edges=[(160,125,160,165),(295,215,345,215),(160,280,160,300),(160,300,790,300),(790,300,790,280)]
def svg_diagram():
 out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 370" role="img" aria-labelledby="t"><title id="t">Azure subscriptions and shared delivery architecture</title><rect width="960" height="370" fill="#0a0e1a"/>']
 for x,y,w,h,title,lines in diagram_nodes:
  out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#141c30" stroke="#22d3ee"/>')
  out.append(f'<text x="{x+14}" y="{y+27}" fill="#e2e8f0" font-family="Arial,sans-serif" font-size="17">{esc(title)}</text>')
  for i,line in enumerate(lines):out.append(f'<text x="{x+14}" y="{y+53+i*27}" fill="#cbd5e1" font-family="Arial,sans-serif" font-size="11">{esc(line)}</text>')
 for x1,y1,x2,y2 in diagram_edges:out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#4ade80" stroke-width="2"/>')
 out.append('<text x="350" y="336" fill="#22d3ee" font-family="Arial,sans-serif" font-size="14">No peering between environment VNets. Each private DNS zone links to its own VNet.</text></svg>')
 return ''.join(out)
(PUBLIC/'architecture.svg').write_text(svg_diagram(),encoding='utf-8')
runtime_rows=[
 ['Flow','Origin','Destination and purpose'],
 ['Operations session','Azure portal / Bastion','Ops VM; Prod Entra user login or local emergency account'],
 ['Application HTTPS','Ops VM 10.30.1.4','Gateway private listener 10.30.4.10:443'],
 ['Backend HTTPS','Application Gateway','App private endpoint 10.30.5.7:443, then App Service'],
 ['Deployment','Private application pool','App SCM private endpoint; package fingerprint verified'],
 ['Application secrets','App outbound VNet integration','Application Key Vault private endpoint 10.30.5.6:443'],
 ['Listener certificate','Gateway managed identity','Certificate vault secret, separately authorized'],
 ['DNS resolution','VNet clients','Internal and privatelink zones; DNS is not an HTTPS hop'],
 ['Diagnostics','Gateway and application vault','Environment Log Analytics and e-mail action groups'],
]
def tablehtml(rows):
 return '<div class="az-table-wrap"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>'
def figure(file,caption=None):
 e=next(x for x in entries if x['file']==file)
 url='azure-case-study/images/'+file
 return f'<figure class="az-evidence"><a href="{url}" target="_blank" rel="noopener"><img src="{url}" width="{e["width"]}" height="{e["height"]}" alt="{esc(e["title"])}" loading="lazy"></a><figcaption>{esc(caption or e["caption"])}</figcaption></figure>'
css='''
/* AZURE CASE STUDY */
#new-azure-project .section-disclosure{max-width:1100px}
.az-lead{font-size:19px;line-height:1.65;color:#cbd5e1;max-width:900px;margin:20px 0}
.az-actions{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}
.az-toc{display:flex;flex-wrap:wrap;gap:8px 18px;margin:22px 0;padding:18px 0;border-block:1px solid var(--border)}
.az-toc a,.az-chapter a,.az-source{color:var(--accent2);text-decoration:underline;text-underline-offset:3px}
.az-chapter{padding:28px 0;border-bottom:1px solid var(--border)}
.az-chapter h3{font-size:24px;font-weight:500;margin-bottom:16px;color:var(--text)}
.az-chapter p{color:#cbd5e1;margin-bottom:16px;max-width:960px}
.az-evidence{margin:22px 0;max-width:100%}
.az-evidence img{display:block;max-width:100%;width:100%;height:auto;border:1px solid var(--border);border-radius:6px}
.az-evidence figcaption{font-size:13px;color:#94a3b8;line-height:1.7;margin-top:12px}
.az-table-wrap{overflow:auto;margin:20px 0}
.az-table-wrap table{border-collapse:collapse;width:100%;min-width:640px;font-size:13px}
.az-table-wrap td,.az-table-wrap th{padding:12px;text-align:left;border-bottom:1px solid var(--border);vertical-align:top}
.az-table-wrap th{color:var(--accent2);background:var(--bg2)}
.az-gallery{margin-top:22px;border:1px solid var(--border);padding:18px;border-radius:8px}
.az-gallery summary{cursor:pointer;font:14px var(--mono);color:var(--accent2);line-height:1.6}
.az-gallery h4{font-size:17px;margin:28px 0 8px}
.az-caption{color:#94a3b8;font-size:13px}
.az-source{font-size:12px;overflow-wrap:anywhere}
@media(max-width:700px){.az-chapter h3{font-size:21px}.az-lead{font-size:16px}.az-gallery{padding:12px}}
/* END AZURE CASE STUDY */
'''
pdfurl='output/pdf/azure-platform-case-study.pdf'
parts=['<section id="new-azure-project"><details class="section-disclosure" open><summary><span class="section-eyebrow">Azure Platform Case Study - Dev / Test / Prod</span></summary><div class="section-content">',
 '<p class="az-lead">A private Azure application platform, deployed across three environments with Terraform, federated CI/CD identities and controlled production access.</p>',
 f'<div class="az-actions"><a class="btn-primary" href="output/pdf/azure-platform-presentation.pdf" download>Download presentation PDF</a><a class="btn-secondary" href="{pdfurl}" download>Download complete case study PDF</a><a class="btn-secondary" href="https://github.com/PeterHudcovic/azure-appservice-platform-lab/tree/{SHA}" target="_blank" rel="noopener">Project source</a></div>',
 '<p class="az-caption">Evidence captured October 2026. Educational lab. Configuration, runtime tests and build records are identified separately.</p>',
 '<div class="az-toc">'+''.join(f'<a href="#az-{c["id"]}">{esc(c["title"])}</a>' for c in chapters)+'</div>']
for c in chapters:
 parts.append(f'<article class="az-chapter" id="az-{c["id"]}"><h3>{esc(c["title"])}</h3><p>{esc(c["text"])}</p>')
 if c['id']=='overview': parts.append(tablehtml(envtable))
 if c['id']=='overview': parts.append('<figure class="az-evidence"><img src="azure-case-study/images/architecture.svg" width="960" height="370" alt="Separate subscriptions and environment networks with shared package delivery"><figcaption>Architecture derived from Terraform and pipeline definitions at the linked source snapshot.</figcaption></figure>')
 if c['id']=='access': parts.append(tablehtml(roles))
 if c['id']=='network': parts.append(tablehtml(runtime_rows)+'<p>VNet flow logs version 2 and Traffic Analytics are configured in layer 1. Foundation policies cover tags, region, vault access and Web App HTTPS/TLS, with explicit exemptions and budget alerts. Build log 14 records non-production compliance exceptions for Azure-created resources and pending production evaluation.</p>')
 if c['image']: parts.append(figure(c['image']))
 parts.append(f'<a class="az-source" href="{SOURCE_URL+c["source"]}" target="_blank" rel="noopener">Source: {esc(c["source"])}</a></article>')
parts.append(f'<article class="az-chapter" id="az-evidence"><h3>Complete evidence gallery</h3><p>{len(entries)} original screenshots, grouped by topic. Open a topic and click an image for its original resolution. Each caption describes the observed result and its limits.</p>')
order=['Overview','Users and access','Managed identities','Shared CI/CD','Production networking and operations','Development','Testing','Monitoring']
for group in order:
 items=[e for e in entries if e['group']==group]
 parts.append(f'<details class="az-gallery"><summary>{esc(group)} ({len(items)} screenshots)</summary>')
 for e in items: parts.append('<h4>'+esc(e['title'])+'</h4>'+figure(e['file']))
 parts.append('</details>')
parts.append('</article></div></details></section>')
section='\n'.join(parts)
def rewrite(text):
 start=text.index('<section id="new-azure-project">')
 end=text.index('<section id="projects">',start)
 text=text[:start]+section+'\n\n'+text[end:]
 text=re.sub(r'/\* AZURE CASE STUDY \*/.*?/\* END AZURE CASE STUDY \*/\s*','',text,flags=re.S)
 return text.replace('</style>',css+'\n</style>',1)
working=(ROOT/'index.html').read_text(encoding='utf-8-sig')
(BUILD/'original-index.html').write_text(working,encoding='utf-8')
(ROOT/'index.html').write_text(rewrite(working),encoding='utf-8')
head=subprocess.check_output(['git','show','HEAD:index.html'],cwd=ROOT).decode('utf-8-sig')
(BUILD/'head-index.html').write_text(head,encoding='utf-8')
(BUILD/'publish-index.html').write_text(rewrite(head),encoding='utf-8')
# Publish only the safe image directory and final PDF, not raw private evidence.
def deployrewrite(text):
 text=text.replace('azure-case-study/images,output/pdf/azure-platform-case-study.pdf,','azure-case-study/images,output/pdf/azure-platform-presentation.pdf,output/pdf/azure-platform-case-study.pdf,')
 return text.replace('source: "index.html,','source: "azure-case-study/images,output/pdf/azure-platform-presentation.pdf,output/pdf/azure-platform-case-study.pdf,index.html,')
workflow=ROOT/'.github/workflows/deploy.yml'
workflow.write_text(deployrewrite(workflow.read_text(encoding='utf-8-sig')),encoding='utf-8')
headwf=subprocess.check_output(['git','show','HEAD:.github/workflows/deploy.yml'],cwd=ROOT).decode('utf-8-sig')
(BUILD/'head-deploy.yml').write_text(headwf,encoding='utf-8')
(BUILD/'publish-deploy.yml').write_text(deployrewrite(headwf),encoding='utf-8')

# A landscape presentation followed by a full-resolution evidence appendix.
PDF=OUT/'azure-platform-case-study.pdf'
cv=canvas.Canvas(str(PDF),pagesize=(960,540),pageCompression=1)
cv.setTitle('Azure Platform Case Study - Peter Hudcovic')
cv.setAuthor('Peter Hudcovic')
page=0
style=ParagraphStyle('body',fontName='Helvetica',fontSize=15,leading=22,textColor=HexColor('#cbd5e1'))
def para(text,x,y,w,size=15,color='#cbd5e1',leading=None):
 st=ParagraphStyle('p',parent=style,fontSize=size,leading=leading or size*1.45,textColor=HexColor(color))
 p=Paragraph(esc(text),st); pw,ph=p.wrap(w,1000); p.drawOn(cv,x,y-ph);return ph
def start(title,subtitle='',size=(960,540)):
 global page
 page+=1;cv.setPageSize(size);w,h=size
 cv.setFillColor(HexColor('#0a0e1a'));cv.rect(0,0,w,h,fill=1,stroke=0)
 titleh=para(title,40,h-35,w-80,28,'#e2e8f0',33)
 if subtitle: para(subtitle,40,h-45-titleh,w-80,11,'#22d3ee')
 cv.setFont('Helvetica',9);cv.setFillColor(HexColor('#94a3b8'))
 cv.drawString(40,18,'Peter Hudcovic / Azure platform lab / October 2026')
 cv.drawRightString(w-40,18,str(page));cv.bookmarkPage('page'+str(page));cv.addOutlineEntry(title,'page'+str(page),0,False)
def imagefit(file,x,y,w,h):
 with Image.open(PUBLIC/file) as im: iw,ih=im.size
 ratio=min(w/iw,h/ih);dw,dh=iw*ratio,ih*ratio
 cv.drawImage(str(PUBLIC/file),x+(w-dw)/2,y+(h-dh)/2,dw,dh,mask='auto')
def sourcefoot(c):
 cv.linkURL(SOURCE_URL+c['source'],(40,36,920,52),relative=0)
 para('Source: '+c['source'],40,49,880,8,'#22d3ee')
start('Azure Platform Case Study','Development / Testing / Production')
para('A private application platform with Terraform and federated CI/CD',40,380,720,34,'#e2e8f0',43)
para('Three environments. Two subscriptions. Separate workload identities and private networks. Production approval, PIM and runtime verification.',40,240,780,19)
para('Peter Hudcovic\nEvidence and build records reviewed October 6, 2026',40,125,700,13,'#94a3b8')
cv.showPage()
for c in chapters:
 start(c['title'],'Configuration and observed results')
 if c['image']:
  para(c['text'],40,420,350,14,leading=20)
  imagefit(c['image'],420,85,500,345)
 else: para(c['text'],40,420,850,20,leading=30)
 sourcefoot(c);cv.showPage()
 if c['id'] in ['overview','access']:
  rows=envtable if c['id']=='overview' else roles
  start('Environment comparison' if c['id']=='overview' else 'Access and permissions matrix','Actual scope and role capabilities')
  st=ParagraphStyle('table',parent=style,fontSize=10.5,leading=14)
  data=[[Paragraph(esc(x),st) for x in row] for row in rows]
  widths=[170,236,236,238] if c['id']=='overview' else [150,375,355]
  tb=Table(data,colWidths=widths)
  tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#141c30')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#1e2d4a')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
  tw,th=tb.wrap(880,425)
  if th>425: raise ValueError('Table too tall '+str(th))
  tb.drawOn(cv,40,440-th);cv.showPage()
 if c['id']=='overview':
  start('Subscriptions and shared delivery','Architecture derived from the source snapshot')
  for x,y,w,h,title,lines in diagram_nodes:
   py=450-y-h
   cv.setFillColor(HexColor('#141c30'));cv.setStrokeColor(HexColor('#22d3ee'));cv.roundRect(x,py,w,h,6,fill=1,stroke=1)
   para(title,x+14,450-y-12,w-28,17,'#e2e8f0')
   for i,line in enumerate(lines):para(line,x+14,450-y-40-i*27,w-28,11)
  cv.setStrokeColor(HexColor('#4ade80'));cv.setLineWidth(2)
  for x1,y1,x2,y2 in diagram_edges:cv.line(x1,450-y1,x2,450-y2)
  para('No VNet peering. Private DNS links remain environment-specific.',345,112,580,14,'#22d3ee');cv.showPage()
 if c['id']=='network':
  start('Production traffic paths','DNS resolves addresses separately from application HTTPS traffic')
  st=ParagraphStyle('flow',parent=style,fontSize=12,leading=17)
  tb=Table([[Paragraph(esc(x),st) for x in row] for row in runtime_rows],colWidths=[155,270,455])
  tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#141c30')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#1e2d4a')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
  tw,th=tb.wrap(880,390);tb.drawOn(cv,40,430-th);cv.showPage()
start('Sources and evidence','Repository snapshot '+SHA[:12])
para('The main presentation follows the requested order: subscriptions, users and permissions, shared delivery, networking, Dev, Test, Prod, monitoring and next steps. The appendix preserves the collected screenshots and their English explanations.',40,415,870,18)
para('Build records 12 and 14 record completed infrastructure pipeline checks, acceptance checks and certificate trust. The access matrix in build record 13 reflects an earlier snapshot; newer pipeline dependency grants are documented in build record 12 and the captured role assignments.',40,285,870,16)
para('Application Insights overview is excluded because it displays a connection string. The original remains in local evidence. Identifiers, resource names and IP addresses are retained. Masked password fields contain no visible password value.',40,175,870,15)
cv.linkURL(SOURCE_URL+'README.md',(40,65,900,90),relative=0)
para('Project source: github.com/PeterHudcovic/azure-appservice-platform-lab',40,85,870,13,'#22d3ee');cv.showPage()
mainpages=page
for group in order:
 for e in [x for x in entries if x['group']==group]:
  size=(842,595) if e['width']/e['height']>1.3 else (595,842)
  w,h=size;start(e['title'],group,size)
  capst=ParagraphStyle('cap',parent=style,fontSize=10,leading=14)
  p=Paragraph(esc(e['caption']),capst);_,ch=p.wrap(w-80,1000)
  titlelines=2 if stringWidth(e['title'],'Helvetica',28)>w-80 else 1
  available=h-190-ch-(33 if titlelines==2 else 0)
  if available<160: raise ValueError('Caption too long: '+e['file'])
  imagefit(e['file'],40,65+ch,w-80,available)
  p.drawOn(cv,40,48);cv.showPage()
cv.save()
from pypdf import PdfReader,PdfWriter
short=PdfWriter()
reader=PdfReader(PDF)
for p in reader.pages[:mainpages]:short.add_page(p)
short.add_metadata({'/Title':'Azure Platform Case Study - Presentation','/Author':'Peter Hudcovic'})
with (OUT/'azure-platform-presentation.pdf').open('wb') as f:short.write(f)
manifest={'sourceCommit':SHA,'screenshots':entries,'excluded':excluded,'chapters':chapters,'pdfPages':page,'mainPages':mainpages}
(ROOT/'azure-case-study'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(BUILD/'build-result.json').write_text(json.dumps({'screenshots':len(entries),'pages':page,'pdfBytes':PDF.stat().st_size,'sourceCommit':SHA},indent=2),encoding='utf-8')
print((BUILD/'build-result.json').read_text())
