# Detekcija pozicija markera 2D

## Reliable detekcija
Odlučili smo da nam je za početak najvažnije imati nekakav *reliable* način za detekciju markera. Nakon isprobavanja dosta rješenja, na kraju smo odlučili koristiti **OpenCV**, specifično **Shi-Tomasi algoritam** jer nam je on dao najbolje rezultate na kocka datasetu.

## Koji marker je koji?
Nakon što smo za svaku sliku dobili točke, idući veliki problem bio je kako skužiti koje točke pripadaju kojem markeru i kako ih povezati među slikama (npr. gornja lijeva točka na markeru 1, koja je to točka na slici 2). 

Tu smo koristili par metoda:
- **Grupiranje točaka:** Upotrijebili smo glupo *hacky* rješenje da ih razdvojimo u grupe ovisno o međusobnoj udaljenosti svih točaka, tako da jedan veliki marker preko cijele slike bi trebao biti jedna grupa, a vise manjih markera po slici bi opet trebali biti svaki u svojoj grupi. 
- **Spajanje između slika:** Mislili smo koristiti poziciju kamere da predvidimo idući *point*, ali to je ispalo preteško s preostalim vremenom. Zato smo izvibecodali rješenje koje pomoću **SIFT** algoritma spaja koje točke na različitim slikama predstavljaju istu točku.
