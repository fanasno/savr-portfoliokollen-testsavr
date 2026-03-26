# SAVR Portföljkollen + TestSAVR

Det här bidraget demonstrerar två produktidéer som skulle kunna stärka SAVR:s erbjudande för både befintliga och nya sparare:

- `SAVR Portföljkollen`
- `TestSAVR`

## Demo

- Publik app: [https://savr-portfoliokollen-testsavr.streamlit.app/](https://savr-portfoliokollen-testsavr.streamlit.app/)
- Videogenomgång: [https://drive.google.com/file/d/1ANp4wm1Xb4fYbysU-LIt6W1zfHU1duEU/view](https://drive.google.com/file/d/1ANp4wm1Xb4fYbysU-LIt6W1zfHU1duEU/view)

Appen är byggd i Streamlit och visar hur SAVR kan hjälpa användare att:

- förstå sin portfölj bättre
- upptäcka koncentrationsrisk och obalanser
- få konkreta rebalanseringsförslag
- få bevakningsnotiser och rebalanseringspåminnelser
- testa investeringsidéer med fiktiva pengar innan riktiga beslut tas

## Idé och kundnytta

### SAVR Portföljkollen
Portföljkollen hjälper användaren att se:

- hur kapitalet är fördelat idag
- om portföljen avviker från vald riskprofil
- vilka innehav eller kategorier som är över- eller underviktade
- hur portföljen kan rebalanseras på ett enkelt och begripligt sätt

Detta skapar kundnytta genom att göra portföljen mer begriplig, minska passiv felallokering och öka sannolikheten att kunden håller sig till sin önskade risknivå över tid.

### TestSAVR
TestSAVR låter användaren prova idéer med ett testbelopp och analysera:

- hur en investering hade utvecklats bakåt i tiden
- hur olika allokeringar påverkar resultatet
- skillnaden mellan buy and hold och återkommande rebalansering
- sannolik framtida utveckling via bootstrap-baserad Monte Carlo

Detta skapar kundnytta genom att sänka tröskeln till investering, öka förståelsen för risk och ge ett pedagogiskt sätt att utforska olika beslut utan verkligt kapital. Funktionen kan också göra det lättare för nya investerare att komma i gång med SAVR.

## Vad demon visar idag

Appen innehåller:

- SAVR-inspirerad layout
- interaktiv portföljanalys
- riskprofil med standardprofiler och egen profil
- riskprofil-enkät
- KPI-kort, viktfördelning och allokeringsjämförelser
- köp- och säljförslag i kronor
- sektion för ny insättning
- bevakning av instrument och exempel på notiser
- TestSAVR med bakåtblick, framåtblick och valbar rebalanseringslogik
- verkliga marknadsserier som referensdata
- publik fondmetadata från SAVR:s öppna katalog

## Så kan SAVR verkställa idén

Nedan är en enkel to do-lista för att gå från demo till produktnära implementation.

### Prioritet 1: Koppla riktiga SAVR-data

1. Ersätt demoportföljen med riktiga kundinnehav från SAVR:s backend.
2. Ersätt Yahoo Finance med SAVR:s godkända eller licensierade marknadsdatakälla.
3. Koppla riktiga historiska NAV-serier för SAVR-fonder i både Portföljkollen och TestSAVR.
4. Säkerställ att risk-, avkastnings- och volatilitetstal beräknas på SAVR:s interna datamodell.

### Prioritet 2: Produktisera Portföljkollen

1. Knyt rebalanseringsmotorn till kundens verkliga riskprofil och lämplighetsbedömning.
2. Låt användaren godkänna föreslagna omviktningar direkt från Portföljkollen.
3. Lägg till tydlig historik för tidigare rebalanseringar och portföljförändringar.
4. Integrera notiser för:
   - bevakade innehav
   - avvikelse från målprofil
   - återkommande rebalanseringspåminnelse

### Prioritet 3: Produktisera TestSAVR

1. Låt användaren testa både SAVR-fonder och andra relevanta instrument i ett pedagogiskt läge.
2. Visa tydligare sannolikhetsband, riskspråk och utfallsintervall.
3. Knyt TestSAVR till innehåll som utbildar nya sparare i:
   - diversifiering
   - rebalansering
   - risk kontra avkastning
4. Lägg till möjligheten att spara scenarier eller gå från testidé till riktig investering.

### Prioritet 4: Drift och infrastruktur

1. Flytta notislogik från Streamlit-demo till SAVR:s scheduler och notiskanaler.
2. Flytta affärslogik från Streamlit-prototyp till SAVR:s ordinarie produktstack.
3. Lägg till loggning, felhantering, övervakning och analys av användarbeteende.
4. Säkerställ intern validering av modellantaganden och riskkommunikation.

## Varför funktionen är kommersiellt intressant

Den här idén kan bidra till:

- högre engagemang i appen
- bättre förståelse för portföljer och risk
- fler återkommande kundinteraktioner via notiser
- ökad trygghet inför investeringsbeslut
- större sannolikhet att nya sparare kommer i gång

Särskilt TestSAVR kan fungera som ett lågtröskelverktyg för att utbilda och konvertera användare från intresse till faktisk investering.

## Metod och nuvarande avgränsningar

- Portfölj- och prisserier bygger i nuvarande version på publikt tillgänglig marknadsdata som referensimplementation.
- Framåtblicken i TestSAVR använder bootstrap-baserad Monte Carlo.
- Riskprofil 1-10 är i nuvarande version en heuristisk skala som översätts till riskramar.
- Nuvarande implementation visar produktlogik och användarupplevelse i ett demoformat, men kan flyttas vidare till SAVR:s ordinarie produktstack.


## Sammanfattning

Det här bidraget visar två kompletterande funktioner:

- `SAVR Portföljkollen` för analys, balans och åtgärdsförslag
- `TestSAVR` för lärande, simulering och tryggare investeringsbeslut

Tillsammans visar de hur SAVR kan stärka både kundnytta, förståelse och produktdifferentiering.
