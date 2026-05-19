# Point Position Detection

Unusable mess :)

Krenuli smo u ovo bez skoro ikakvog iskustva u computer grafici, ali smo pokusali rastaviti zadatak na nekakve jednostavnije zadatke koje mozemo medusobno podjeliti.

Odlucili smo krenuti s detekcijom pozicija markera, jer je to slicnost koju svi testni podatci dijele i to nam se cinilo kao nekakva osnova na koju bi dalje gradili.

Za to smo se podjelili na 3 dijela:

- [Detekcija pozicija markera 2d](DETEKCIJA_2D.md)
- [Odredivanje 3d pozicije markera pomocu pozicije kamere i triangulacije](TRIANGULACIJA.md)
- [Prikazivanje 3d tocaka u prostoru za vizualizaciju i provijeru tocnosti rezultata](PRIKAZ.md)

Kako pokrenuti:
instaliraj requirements iz requirements.txt, napravi venv, conda whatever
pokreni iz project roota

> Potrebno je dodati dataset slike!

```python
python3 src/main.py
```

Tokom rijesavanja naisli smo na mnoge probleme (u detaljnim opisima stepova pise vise) koje smo rijesili uglavnom vibecodanjem. Projekt je spor i neiskoristivo u realnim situacijama, ali sada imamo puno bolju ideju razlicitih nacina za rijesavanje koje bi mogli dosta detaljnije napraviti da imamo vise vremena.
