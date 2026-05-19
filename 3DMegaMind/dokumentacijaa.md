# STEM Games 2026 – Dokumentacija razvoja projekta
### 3D Rekonstrukcija oblaka točaka iz stereo slika

---

## 1. Uvod i razumijevanje problema

Kad smo dobili zadatak, cilj je bio jasan ali tehnički izazovan: iz više fotografija istog objekta snimljenih iz različitih kutova rekonstruirati 3D oblak točaka (point cloud). Imali smo 4 dataseta:

| Dataset | Poznate koordinate kamera? | Rezolucija | Napomena |
|---|---|---|---|
| **Box** | ✅ Da | 1920 × 1080 | Kamera FOV 90° |
| **Entrance** | ✅ Da | 1920 × 1080 | Kamera FOV 90° |
| **Statue** | ❌ Ne | varijabilno | FOV 90° |
| **Fountain** | ❌ Ne | 3072 × 2048 | FOV ~84° |

Za **Box** i **Entrance** imali smo `.txt` datoteke s egzaktnim pozicijama kamera (`CamPosition`, `CamForward`, `CamRight`, `CamUp`). Za **Statue** i **Fountain** kamera je bila potpuno nepoznata – što je predstavljalo znatno teži problem.

---

## 2. Zajednički tehnološki temelj

Bez obzira na to jesu li pozicije kamera poznate ili ne, cijeli se projekt oslanja na iste bazične koncepte računalnog vida, detekcije značajki i prikaza podataka.

### 2.1 Geometrija kamera i jednadžba zrake iz piksela
Zadatak nam je u uputama dao C++ kod funkcije `GetLineEquation()`, koji smo portirali u Python. Formula obavlja projekciju piksela iz 2D prostora slike u 3D smjerni vektor:


```

coeffRight = 2.0 * (pixelCol - resX/2.0 + 0.5) / resX
coeffUp    = -2.0 * (pixelRow - resY/2.0 + 0.5) / resY * (resY / resX)
Direction  = CamForward + coeffRight * CamRight + coeffUp * CamUp

```

Za svaki piksel dobivamo zraku koja prolazi kroz položaj kamere i tu točku u 3D prostoru. Za FOV od 90°, skala je `tan(45°) = 1.0`. Za Fountain s FOV-om od 84° koristili smo `tan(42°) ≈ 0.9004`.

Python implementacija završila je u `triangulate.py`:
```python
def get_line_equation(pixel_row, pixel_col, res_x, res_y, cam, fov_scale=1.0):
    coeff_right = 2.0 * (pixel_col - res_x / 2.0 + 0.5) / res_x
    coeff_up = -2.0 * (pixel_row - res_y / 2.0 + 0.5) / res_y
    coeff_up = coeff_up * res_y / res_x
    coeff_right *= fov_scale
    coeff_up *= fov_scale
    direction = cam_fwd + coeff_right * cam_rgt + coeff_up * cam_up
    direction = direction / np.linalg.norm(direction)
    return cam_pos, direction

```

### 2.2 Detekcija značajki: SIFT i Lowe's Ratio Test

Da bismo uopće mogli upariti piksele između dviju slika iste scene, koristili smo **SIFT (Scale-Invariant Feature Transform)** iz OpenCV-a. SIFT pronalazi stabilne ključne točke i opisuje ih vektorom od 128 dimenzija.

Za filtriranje lažnih i dvosmislenih uparivanja implementirali smo **Lowe's ratio test**: tražimo dva najbliža susjedna deskriptora i zadržavamo uparivanje samo ako je:

```
distance(m1) < ratio * distance(m2)

```

Inicijalno smo krenuli sa standardnih `ratio = 0.75`.

### 2.3 Vizualizator (Web aplikacija)

Kako bismo verificirali rezultate, paralelno smo razvili **web-based 3D vizualizator** u `Visualizer/` direktoriju:

* **Backend:** Python HTTP server (`server.py`) koji servira statičke datoteke, API rute za metapodatke kamera, te oblak točaka u binarnom formatu.
* **Frontend:** Three.js za fluidno renderiranje točaka u browseru s orbitalnom navigacijom i konusima vidnog polja kamera.
* **Caching:** Server automatski kompajlira teške CSV datoteke u brzi binarni format (`.bin`, packed `float32 + RGBA bytes`). Ako detektira da je CSV izmijenjen, sam pokreće rekompilaciju.
* **Konfiguracija (`config.txt`):** Putanje do datoteka definirane su po datasetu:
```ini
box_csv_path = TestImages/Box/box.csv
entrance_csv_path = TestImages/Entrance/entrance.csv
```

---

## 3. Prvi scenarij: Triangulacija za Box i Entrance (Poznate kamere)

Ovdje smo imali sve egzogene parametre kamera u tekstualnim datotekama, pa smo se fokusirali na čistu geometriju triangulacije i optimizaciju guste rekonstrukcije.

### 3.1 Matematika triangulacije: Presjecište dviju 3D zraka
Zrake iz dviju kamera koje gledaju istu točku u prostoru se zbog numeričkih grešaka i šuma u detekciji gotovo nikada neće idealno sjeći. Koristili smo metodu **minimalne distance između dvaju pravaca u 3D** (closest point approach):

```

Zraka 1: Q1 = p1 + t1 * d1
Zraka 2: Q2 = p2 + t2 * d2

Rješavamo sustav 2×2 jednadžbi za t1 i t2 koji minimizira udaljenost.
Procijenjena 3D točka: midpoint( Q1, Q2 )
Greška rekonstrukcije: || Q1 - Q2 ||

```

### 3.2 Neuspješni pokus: custom kodirano rješenje: repozitorij za Checkerboard + PnP
Prije nego što smo učitali gole `.txt` podatke, htjeli smo provjeriti automatizirani pipeline koji je razvio kolega iz tima. Ideja je bila:
1. Detektirati checkerboard uzorak (2×2) na pozadini slika.
2. Iskoristiti poznate world koordinate tog uzorka i kroz **PnP (Perspective-n-Point)** solver automatski izračunati pozicije kamera.

**Zašto to nismo iskoristili:** Repozitorij nije bio usklađen s našim koordinatnim sustavom, detekcija uzorka je pucala pod varijabilnim osvjetljenjem i nismo imali vremena za duboki debugging. Odustali smo i prešli na čitanje koordinata izravno iz `boxInput.txt` i `entranceInput.txt`.

### 3.3 Inicijalni pipeline i problem premalo točaka
Prva verzija pipelinea u `triangulate.py` pratila je korake:

```

Učitaj kamere -> SIFT detekcija -> Brute-Force Matching -> Lowe's Ratio Test -> RANSAC + Fundamentalna matrica -> Triangulacija -> Photo-consistency check -> SOR filtar -> CSV

```
Inicijalni run za **Box** vratio je svega **~16,000 točaka**. Zidovi kocke bili su prazni zbog prestrogih SIFT parametara (`nfeatures=15000`, `contrastThreshold=0.01`) i preniskog ratio praga (`0.75`). Najveći problem bio je **Photo-consistency check** (provjera boje u trećim kamerama) – uvjet da barem 30% ostalih kamera mora potvrditi boju odbacivao je točke na bokovima jer su zbog okluzija (skrivanja) bile vidljive iz samo 1-2 kuta.

### 3.4 Rješenje: Adaptivni parametri po datasetu
Za Box i Entrance smo **potpuno isključili photo-consistency provjeru** i ublažili SIFT pragove:
```python
if dataset_name.lower() in ["box", "entrance"]:
    sift = cv2.SIFT_create(nfeatures=40000, contrastThreshold=0.005, edgeThreshold=30)
    ratio_thresh = 0.82
    ransac_thresh = 1.5
    max_err_base = 1.5
    max_err_ratio = 0.02

```

SOR (Statistical Outlier Removal) filtar smo također ublažili s faktora `1.2` na `1.5` standardnih devijacija kako ne bismo agresivno brisali rubne dijelove objekata.

### 3.5 Rezultati optimizacije

| Dataset | Prije optimizacije | Nakon optimizacije | Ishod |
| --- | --- | --- | --- |
| **Box** | ~16,000 točaka | **46,725 točaka** | **~3× više točaka, jasni rubovi** |
| **Entrance** | ~32,037 točaka | **64,597 točaka** | **~2× više točaka, kontinuitet površine** |

---

## 4. Drugi scenarij: Fountain i Statue (Nepoznate kamere)

Za datasete bez poznatih pozicija kamera, problem je bio dramatično složeniji jer nismo imali bazične parametre za jednadžbu zrake.

### 4.1 Istraživanje i slijpe ulice

* **Pokušaj ručnog pogađanja kamera:** Brzo odbačeno kao matematički nemoguća misija zbog previše stupnjeva slobode.
* **OpenCV SfM modul:** Pokušali smo iskoristiti ugrađeni `sfm` modul, no on zahtijeva specifičnu kompilaciju `opencv-contrib` biblioteke s vanjskim solverima koja nam nije bila dostupna u radnom okruženju.
* **Custom PnP pristup:** Pokušaj s detekcijom checkerboarda (iz sekcije 3.2) ovdje je također zakazao jer na ovim prirodnim i otvorenim scenama nismo imali postavljen kontrolni uzorak.

### 4.2 Rješenje: Uvođenje COLMAP-a

Problem smo uspješno premostili uvođenjem alata **COLMAP** (industrijski standard za Structure-from-Motion). COLMAP je preuzeo slike za **Fountain** i **Statue**, proveo internu SIFT ekstrakciju, procijenio intrinsične i ekstrinsične parametre kamera, te kroz korake *Sparse* i *Dense* (Multi-View Stereo) rekonstrukcije generirao guste oblake točaka.

Izlazni `.ply` format smo potom filtrirali kako bismo izvukli isključivo bazične geometrijske i kolorističke informacije koje naš vizualizator očekuje: `X, Y, Z, R, G, B`.

### 4.3 Naknadna obrada i dorada neobrađenih podataka

Nakon dobivanja inicijalnih oblaka točaka za nepoznate kamere, morali smo ručno intervenirati na anomalijama u podacima:

#### Fontana (Fountain) – Skaliranje koordinata

Prilikom inicijalne pripreme `fountain.csv` datoteke, primijetili smo da su vrijednosti u čudnim omjerima:

* Prvo smo greškom sve koordinate pomnožili sa 1000, što je razbacalo točke u ogroman prostor i uzrokovalo raspad vizualizacije.
* Nakon analize, korigirali smo transformaciju na **množenje sa 100**, što je dalo savršeno smislene i stabilne koordinate unutar Three.js scene.

#### Transformacija izdvojenog objekta (`objekt.csv`)

U sklopu dobivenog Fountain dataseta, `objekt.csv` (~14,000 točaka) bila je fizikalno dezorijentirana – objekt je bio nagnut prema naprijed pod oštrim kutom.

Za ispravljanje smo koristili **4×4 homogenu matricu transformacije** u skripti `transform.py`:

```
H = | R  |  t  |
    | 0  |  1  |

```

1. Izračunali smo centroid oblaka kako bismo rotirali oko centra objekta.
2. Primijenili smo rotaciju za `+90° oko X osi`:
```
R_x(90°) = [[1,  0,  0],
            [0,  0, -1],
            [0,  1,  0]]


```




3. To je uspravilo objekt, ali je os i dalje bježala. Nakon toga smo probali rotaciju oko Z osi za 180° što je dalo bolji rezultat.
4. Kako bismo izbjegli beskrajno "slijepe" pokušaje u kodu, u `transform.py` smo ugradili interaktivni vizualizator (`matplotlib`) koji nam je omogućio da tipkama na tipkovnici rotiramo objekt za 90° po svim osima u realnom vremenu dok vizualno nismo bili zadovoljni, a tek onda trajno zapisali `transformirani_objekt.csv`.

---

## 5. Point Cloud Completer (Zgušnjavanje i čišćenje)

Za završno poliranje svih generiranih oblaka točaka (bilo iz našeg pipelinea ili iz COLMAP-a), razvili smo modul `Completer/completer.py`. Njegova je svrha popunjavanje praznina na površinama metodom **lokalne interpolacije površine** (Local Surface Interpolation).

Kako bismo izbjegli sporu $O(n^2)$ pretragu, koristili smo **cKDTree** iz knjižnice `scipy`:
```python
def local_surface_interpolation(self, df, k=6, min_dist=8.0, max_dist=35.0):
    # Za svaku točku: kroz cKDTree pronalazimo k najbližih susjeda
    # Za svaki par (točka, susjed): ako je udaljenost unutar [min_dist, max_dist],
    # interpoliramo novu točku na točnoj sredini tog segmenta.
    # Boja nove točke računa se kao srednja vrijednost (RGB) krajnjih točaka.

```

Nakon interpolacije, novi gušći oblak prolazi kroz **Radius Outlier Removal (ROR)** filtar koji uklanja šum i "lebdeće" točke nastale pogrešnim sparivanjem:

```python
def apply_radius_outlier_removal(self, df, radius, min_neighbors):
    tree = cKDTree(xyz)
    indices_list = tree.query_ball_point(xyz, r=radius)
    mask = [len(indices) >= min_neighbors for indices in indices_list]
    return df[mask]

```

Cijeli ovaj završni proces povezan je u glavnu upravljačku skriptu **`3DMegaMind.py`**, koja sekvencijalno pokreće triangulaciju, izvršava zgušnjavanje kroz `Completer`, osvježava konfiguraciju vizualizatora i podiže lokalni web server.

---

## 6. Sažetak algoritama i arhitekture

### Pregled korištenih algoritama

| Algoritam | Namjena | Biblioteka / Izvor |
| --- | --- | --- |
| **SIFT** | Detekcija značajki otpornih na rotaciju i skalu | OpenCV |
| **Brute-Force Matching** | Uparivanje deskriptora između parova slika | OpenCV |
| **Lowe's Ratio Test** | Filtriranje dvosmislenih uparivanja | Ručna implementacija |
| **RANSAC + Fundamental Matrix** | Epipolarno filtriranje (odbacivanje geometrijskih outliera) | OpenCV |
| **Ray-Ray Triangulation** | Rekonstrukcija 3D točke iz dviju zraka (Closest point) | Ručna implementacija (NumPy) |
| **Photo-Consistency Check** | Validacija boje kroz projekciju u treće kamere | Ručna implementacija |
| **SOR (Statistical Outlier Removal)** | Uklanjanje izoliranih točaka na temelju statistike udaljenosti | `scipy.spatial.cKDTree` |
| **ROR (Radius Outlier Removal)** | Uklanjanje točaka s premalo susjeda unutar radijusa | `scipy.spatial.cKDTree` |
| **Local Surface Interpolation** | Generiranje novih točaka na sredinama segmenata za zgušnjavanje | `scipy.spatial.cKDTree` |
| **Homogena matrica transformacije** | Korekcija nagiba i orijentacije oblaka točaka (4×4) | NumPy |
| **PnP (Perspective-n-Point)** | Pokušaj procjene pozicije kamera preko checkerboarda | OpenCV (Nekorišteno u finalu) |

### Struktura projekta

```
zzStemGames2026_ProjectTask/
│
├── 3DMegaMind/                     ← SVE AKTIVNO KORIŠTENO U FINALNOM RADU
│   ├── 3DMegaMind.py                # Master launcher: izbornik, server, completion
│   ├── triangulate.py               # Triangulacija za Box i Entrance
│   ├── DOKUMENTACIJA.md             # Ova dokumentacija
│   ├── STEM_Games_2026__Project.pdf # Originalni zadatak
│   ├── project_text.txt             # Tekst zadatka
│   │
│   ├── Completer/
│   │   └── completer.py             # Modul za zgušnjavanje oblaka točaka
│   │
│   ├── PnP/
│   │   ├── pnp_solver.py            # PnP solver (opcija 5 u izborniku)
│   │   └── pnp_documentation.md
│   │
│   ├── Visualizer/
│   │   ├── server.py                # Python HTTP server za web vizualizator
│   │   ├── config.txt               # Putanje do CSV datoteka po datasetu
│   │   └── static/                  # HTML, CSS, JS frontend (Three.js)
│   │
│   └── TestImages/
│       ├── Box/
│       │   ├── box1.png ... box12.png
│       │   ├── boxInput.txt         # Koordinate 12 kamera
│       │   └── box.csv              # Oblak točaka – triangulacija (46,725 točaka)
│       ├── Entrance/
│       │   ├── entrance1.png ... entrance12.png
│       │   ├── entranceInput.txt
│       │   └── entrance.csv         # Oblak točaka – triangulacija (64,597 točaka)
│       ├── Statue/
│       │   ├── statue*.jpg
│       │   └── statue.csv           # Oblak točaka – dobiven preko COLMAP-a
│       └── Fountain/
│           ├── fountain*.jpg
│           └── fountain.csv         # Oblak točaka – dobiven preko COLMAP-a
│
└── SMECE/                           ← EKSPERIMENTALNI / NEKORIŠTEN KOD TIJEKOM ITERACIJA
    ├── debug_triangulation.py
    ├── find_centers.py
    ├── solve_consistent_pnp.py
    ├── test_pnp_on_box.py
    ├── transform.py / transform_final.py
    ├── generate_coco.py
    ├── objekt.csv
    ├── Visualizer.zip
    └── point-position-detection/    ← repo (checkerboard detekcija)

```

---

## 7. Ključne lekcije i plan za budućnost

### Što je dobro funkcioniralo:

* **SIFT + RANSAC + Triangulacija** dala je izvrstan, matematički čist rezultat na poznatim kamerama.
* **Per-dataset tuniranje parametara** drastično je spasilo gustoću točaka na nekim teksturalno siromašnim površinama (poput kutije).
* **Binarizacija podataka (`.bin` cache)** uklonila je usko grlo mrežnog prijenosa i omogućila trenutno učitavanje stotina tisuća točaka u browseru.

### Što je podbacio / Izazovi:

* **Photo-consistency** previše pretpostavlja idealne uvjete bez okluzija. Na realnim objektima s oštrim bridovima (Box) više šteti nego što pomaže.
* **Akumulacija pogreške (Drift) kod PnP-a** – bez implementiranog globalnog mehanizma izravnanja zraka (Bundle Adjustment), parcijalno dodavanje kamera preko PnP-a brzo divergira.

### Budući standardizirani workflow:

Iskustvo iz natjecanja pokazuje da je najrobustniji i najbrži produkcijski pipeline zapravo potpuni oslonac na COLMAP za bazičnu rekonstrukciju, nakon čega slijedi naš custom razvoj za obradu:

```
Slike -> COLMAP (SfM + MVS) -> Ekstrakcija (X,Y,Z,R,G,B) -> Standardizirani CSV -> Completer -> Web Visualizer

```

Odabir **CSV formata** pokazao se idealnim kao središnji korak jer omogućuje maksimalno modularan pristup: ljudima je čitljiv, trivijalan je za debugiranje, a Python (`pandas`) ga u kombinaciji s našim automatskim `.bin` kompajlerom žvače u milisekundama.

Dodatno, za većinu vizualizacije korištena je Umjetna Inteligencija zbog boljeg dizajna i da uštedimo vrijeme na sam pipeline i workflow, te smo ga koristili za istraživanje algoritama i alata koji već rade dio pipeline-a. Ručno je kodiran pokušaj dobivanja točaka checkerboarda i fine-tunning vizualizacije i sitnih grešaka u triangulaciji.

---

*Dokumentacija ažurirana i strukturirana 19. svibnja 2026. u sklopu STEM Games Technology Arene.*

```
