# Barcode Extractor

Kleine Windows-tool om barcodes uit PDF-bestanden te halen.

## Werking

1. Zet PDF-bestanden in `input`
2. Start `run.bat`
3. Klik op **Scan input map**
4. De PDF wordt gescand
5. Zodra een barcode wordt gevonden, wordt de PDF gekopieerd naar `output`
6. De barcode wordt de nieuwe bestandsnaam

Voorbeeld:

```
input/
  artwork.pdf

output/
  8710675274027.pdf
```

## Eerste installatie

Dubbelklik één keer op:

```
setup.bat
```

Daarna gebruik je alleen:

```
run.bat
```

## Handmatig installeren

```bash
python -m pip install -r requirements.txt
python app.py
```

## Mappen

De applicatie maakt automatisch deze structuur:

```
barcode_extractor/
├── app.py
├── input/
├── output/
├── requirements.txt
├── setup.bat
└── run.bat
```
