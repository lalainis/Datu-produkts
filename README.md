# Enerģijas patēriņa optimizācijas panelis

Šī ir web aplikācija ar Python backend un interaktīvu dashboard frontend, kas izmanto:

- [Promt.docx](./Promt.docx) prasības
- [Dati_prototipesanai.xlsx](./Dati_prototipesanai.xlsx) vēsturiskā patēriņa datus
- [NP_Cenas_LV.xlsx](./NP_Cenas_LV.xlsx) Nord Pool cenu datus

## Ko rāda aplikācija

- ieteikumus energoefektivitātei
- ieteikumus patēriņa pārcelšanai uz lētākām stundām
- novērtējumu, vai var samazināt atļauto slodzi
- anomālu patēriņa notikumu sarakstu
- iespēju precizēt modeli ar telpu platību, iekārtu skaitu un jaudu

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
