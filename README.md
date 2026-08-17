# Enerģijas patēriņa optimizācijas panelis

Šī ir web aplikācija ar Python backend un interaktīvu dashboard frontend, kas izmanto:

- [Promt.docx](./Promt.docx) prasības
- [ofisu komplekss.xlsx](./ofisu%20komplekss.xlsx), [Razotne ar SES.xlsx](./Razotne%20ar%20SES.xlsx) un [Tirdzniecibas_centrs_ar SES un EU.xlsx](./Tirdzniecibas_centrs_ar%20SES%20un%20EU.xlsx) vēsturiskā patēriņa datus
- [NP_Cenas_LV.xlsx](./NP_Cenas_LV.xlsx) Nord Pool cenu datus

## Ko rāda aplikācija

- ieteikumus energoefektivitātei
- ieteikumus patēriņa pārcelšanai uz lētākām stundām
- novērtējumu, vai var samazināt atļauto slodzi
- lokālu AI konsultanta kopsavilkumu, ja ir pieejams Ollama modelis
- anomālu patēriņa notikumu sarakstu
- iespēju precizēt modeli ar telpu platību, iekārtu skaitu un jaudu
- datu importa faila izvēli pie palaišanas

## Arhitektūra

- [server.py](./server.py) - Flask backend, kas servē UI un API endpointus
- [backend_service.py](./backend_service.py) - datu ielāde, kopsavilkumi un scenāriju aprēķini
- [app.js](./app.js) - frontend, kas izmanto `/api/bootstrap` un `/api/dashboard`
- [scripts/generate_data.py](./scripts/generate_data.py) - Excel datu pārveide uz `data/app-data.json`

## Palaišana

1. Pārģenerē datus, ja Excel faili ir mainīti:

   ```powershell
   python scripts\generate_data.py
   ```

2. Uzinstalē Python atkarības:

   ```powershell
   pip install -r requirements.txt
   ```

3. Startē backend serveri:

   ```powershell
   python server.py
   ```

4. Atver pārlūkā:

   ```text
   http://127.0.0.1:8010
   ```

## Lokālais AI konsultants

Lai panelī parādītos pilnīgi automātiskais AI konsultants, palaid lokālu [Ollama](https://ollama.com/) servisu un modeli, piemēram:

```powershell
ollama run llama3.1:8b
```

Pēc noklusējuma aplikācija mēģina sasniegt:

- `LOCAL_AI_BASE_URL=http://127.0.0.1:11434`
- `LOCAL_AI_MODEL=llama3.1:8b`

Ja lokālais modelis nav pieejams, aplikācija turpina strādāt ar aprēķinu bāzētajiem ieteikumiem un AI panelī parāda statusu, ka lokālais AI nav sasniedzams.

## Failu struktūra

- `index.html` - dashboard struktūra
- `styles.css` - production-style vizuālais noformējums
- `app.js` - API patērējošs frontend
- `server.py` - backend entrypoint
- `backend_service.py` - aprēķinu un datu sagatavošanas loģika
- `scripts/generate_data.py` - Excel datu pārveide uz `data/app-data.json`

## API endpointi

- `GET /api/health` - backend veselības pārbaude
- `GET /api/bootstrap` - globālais kopsavilkums un objektu saraksts
- `GET /api/dashboard?objectId=...&area=...&equipmentCount=...&equipmentPowerWatts=...` - objekta scenārija aprēķins
