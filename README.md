# Point Position Detection

Unusable mess :)

Krenuli smo u ovo bez skoro ikakvog iskustva u računalnoj grafici, ali smo pokušali rastaviti zadatak na nekakve jednostavnije zadatke koje možemo međusobno podijeliti.

Odlučili smo krenuti s detekcijom pozicija markera, jer je to sličnost koju svi testni podaci dijele i to nam se činilo kao nekakva osnova na kojoj bismo dalje gradili.

## Struktura projekta
Za to smo se podijelili na 3 dijela:

- **[Detekcija pozicija markera 2D](DETEKCIJA_2d.md)**
  - Kako uopće skužiti gdje su točke na slici i povezati ih.
- **[Određivanje 3D pozicija markera pomoću pozicije kamere i triangulacije](TRIANGULACIJA.md)**
- **[Određivanje 3D pozicija markera COLMAP-om](COLMAP.md)**
  - Kako od tih 2D točaka i pozicije kamere dobiti stvarne 3D točke u prostoru.
- **[GLAVNA DOKUMENTACIJA](3DMegaMind/dokumentacijaa.md)**

## Kako pokrenuti

1. Instaliraj requirements iz `requirements.txt`, napravi `venv`, `conda` *whatever*
2. Pokreni iz root direktorija projekta

> Potrebno je dodati dataset slike!

```python
python3 src/main.py
```

## Disclaimer
Tijekom rješavanja naišli smo na mnoge probleme (u detaljnim opisima koraka piše više) koje smo riješili uglavnom vibe-codingom. Projekt je spor i neiskoristiv u realnim situacijama, ali sada imamo puno bolju ideju različitih načina za rješavanje koje bismo mogli dosta detaljnije napraviti da imamo više vremena i znanja.

