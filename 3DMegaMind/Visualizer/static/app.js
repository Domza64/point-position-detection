// --- STEM Games 2026 - 3D Visualizer & Alignment Tool ---

// State variables
let scene, camera, renderer, controls;
let pointCloud = null;          // loaded from server or custom file
let syntheticPoints = null;     // generated in frontend
let cameraHelpers = [];         // frustum wireframes in scene
let activeDataset = null;
let datasetConfig = {};         // config retrieved from API
let activeCameraId = "free";    // "free" or camera index (1-based)
let activeK = null;             // camera intrinsic parameters

// Points data stores
let basePointsData = {
    positions: null, // Float32Array (original loaded points)
    colors: null     // Float32Array (normalized 0-1)
};

let loadedPointsData = {
    positions: null, // Float32Array (filtered points displayed)
    colors: null     // Float32Array (normalized 0-1)
};

let filtersState = {
    zHeightEnabled: false,
    minZ: -200,
    maxZ: 424,
    
    rorEnabled: false,
    rorRadius: 15.0,
    rorMinNeighbors: 3,
    
    sorEnabled: false,
    sorNeighbors: 16,
    sorStdRatio: 1.2,
    
    interpolateEnabled: false,
    interpolateK: 6,
    interpolateMinDist: 8.0,
    interpolateMaxDist: 35.0
};

let syntheticPointsData = {
    positions: null,
    colors: null
};

// Alignment transforms for loaded point cloud
let pointCloudTransform = {
    tx: 0, ty: 0, tz: 0,
    rx: 0, ry: 0, rz: 0, // degrees
    scale: 1.0
};

// Synthetic primitive parameters
let syntheticParams = {
    shape: 'cube',
    tx: 0, ty: 0, tz: 110,
    w: 80, h: 80, d: 80,
    rx: 0, ry: 0, rz: 0, // degrees
    density: 40,
    show: false
};

// Colors mapping
const COLOR_MODE = {
    RGB: 'rgb',
    ELEVATION: 'elevation',
    DEPTH: 'depth',
    SOLID: 'solid'
};
let activeColorMode = COLOR_MODE.RGB;
let solidPointColor = new THREE.Color("#58a6ff");

// Init application on load
window.addEventListener('DOMContentLoaded', () => {
    initThree();
    setupUIEventHandlers();
    loadDatasetsList();
    animate();
});

// --- THREE.JS INITIALIZATION ---
function initThree() {
    const container = document.getElementById('canvas-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Create scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0d10);

    // Create camera
    // Default FOV will be updated when camera is locked
    camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 5000);
    camera.position.set(0, 300, 150);
    camera.up.set(0, 0, 1); // Set world UP vector to Z axis to match dataset

    // Create renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    document.getElementById('webgl-canvas-target').appendChild(renderer.domElement);

    // Add OrbitControls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxDistance = 3000;
    controls.minDistance = 2;

    // Add lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(200, 400, 200);
    scene.add(dirLight);

    // Add grid helper (XY plane to match dataset)
    const gridHelper = new THREE.GridHelper(1000, 50, 0x388bfd, 0x1f242c);
    gridHelper.rotation.x = Math.PI / 2;
    gridHelper.name = "grid-helper";
    scene.add(gridHelper);

    // Add coordinate axes helper
    const axesHelper = new THREE.AxesHelper(150);
    axesHelper.name = "axes-helper";
    scene.add(axesHelper);

    // Watch resize
    window.addEventListener('resize', onWindowResize);
}

function onWindowResize() {
    const container = document.getElementById('canvas-container');
    const width = container.clientWidth;
    const height = container.clientHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}

// --- DATASET & DATA LOADING ---
async function loadDatasetsList() {
    try {
        const response = await fetch('/api/datasets');
        const datasets = await response.json();

        const select = document.getElementById('dataset-select');
        select.innerHTML = '';

        datasets.forEach(ds => {
            const opt = document.createElement('option');
            opt.value = ds.name;
            opt.textContent = `${ds.name} (${ds.resolution.width}x${ds.resolution.height})`;
            select.appendChild(opt);
        });

        if (datasets.length > 0) {
            select.value = datasets[0].name;
            loadDataset(datasets[0].name);
        }
    } catch (e) {
        console.error("Error loading datasets list:", e);
    }
}

async function loadDataset(name) {
    activeDataset = name;
    activeCameraId = "free";

    // Reset inputs
    document.getElementById('image-opacity').value = 0;
    document.getElementById('opacity-val').textContent = 0;
    document.getElementById('image-overlay').style.opacity = 0;
    document.getElementById('camera-select').value = "free";
    document.getElementById('lock-view-toggle').checked = false;
    document.getElementById('lock-view-toggle').disabled = true;

    // Retrieve dataset config (resolution, cameras list, intrinsics K)
    const configRes = await fetch(`/api/dataset/${name}/cameras`);
    datasetConfig = await configRes.json();
    activeK = datasetConfig.K;

    // Update aspect ratio of container
    const container = document.getElementById('canvas-container');
    let aspect = 16 / 9; // Box, Entrance, Statue
    if (name.toLowerCase() === 'fountain') {
        aspect = 3 / 2; // Fountain 3072x2048
    }
    container.style.aspectRatio = aspect;
    onWindowResize();

    // Populate cameras selector
    const camSelect = document.getElementById('camera-select');
    camSelect.innerHTML = '<option value="free">Free Orbit Camera</option>';

    datasetConfig.cameras.forEach(cam => {
        const opt = document.createElement('option');
        opt.value = cam.id;
        opt.textContent = `Camera ${cam.id}`;
        camSelect.appendChild(opt);
    });

    document.getElementById('cameras-count').textContent = datasetConfig.cameras.length;

    // Create camera frustums in 3D scene
    buildCameraFrustums(datasetConfig.cameras);

    // Fetch and load point cloud
    await loadPointCloud(name);

    // Generate synthetic points
    generateSyntheticPrimitive();

    // Reset transformations
    resetPointCloudTransforms();
}

async function loadPointCloud(datasetName) {
    const loader = document.getElementById('image-loading-indicator');
    loader.classList.remove('hidden');
    loader.querySelector('span').textContent = "Downloading point cloud buffer...";

    try {
        const response = await fetch(`/api/dataset/${datasetName}/points`);
        if (!response.ok) throw new Error("API returned error");

        const buffer = await response.arrayBuffer();
        const numPoints = buffer.byteLength / 16; // 12 bytes XYZ + 4 bytes RGBA

        const positions = new Float32Array(numPoints * 3);
        const colors = new Float32Array(numPoints * 3);
        const view = new DataView(buffer);

        for (let i = 0; i < numPoints; i++) {
            const offset = i * 16;
            // Float32 (XYZ)
            positions[i * 3] = view.getFloat32(offset, true);
            positions[i * 3 + 1] = view.getFloat32(offset + 4, true);
            positions[i * 3 + 2] = view.getFloat32(offset + 8, true);

            // Uint8 (RGB)
            colors[i * 3] = view.getUint8(offset + 12) / 255;
            colors[i * 3 + 1] = view.getUint8(offset + 13) / 255;
            colors[i * 3 + 2] = view.getUint8(offset + 14) / 255;
        }

        basePointsData.positions = positions;
        basePointsData.colors = colors;

        // Auto-configure filters defaults depending on dataset
        initFilterDefaults(datasetName);

        // Apply filters (which will populate loadedPointsData and render)
        applyFilters();

    } catch (e) {
        console.error("Error loading point cloud:", e);
        document.getElementById('points-count').textContent = "0 (Failed to load)";
    } finally {
        loader.classList.add('hidden');
    }
}

// Render points using Three.js Points
function renderPointsMesh() {
    if (pointCloud) {
        scene.remove(pointCloud);
    }

    if (!loadedPointsData.positions || loadedPointsData.positions.length === 0) return;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(loadedPointsData.positions, 3));

    // Apply initial colors based on mode
    applyColorsAttribute(geometry, loadedPointsData, false);

    const size = parseFloat(document.getElementById('point-size').value);
    const material = new THREE.PointsMaterial({
        size: size,
        vertexColors: true,
        sizeAttenuation: true,
        transparent: true,
        opacity: 0.85
    });

    pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);
}

// Function to apply colors based on mode
function applyColorsAttribute(geometry, pointsData, isSynthetic = false) {
    const numPoints = pointsData.positions.length / 3;
    const colors = new Float32Array(numPoints * 3);

    if (activeColorMode === COLOR_MODE.RGB && pointsData.colors) {
        // Direct colors
        colors.set(pointsData.colors);
    }
    else if (activeColorMode === COLOR_MODE.ELEVATION) {
        // Color by Z coordinate height
        let minZ = Infinity, maxZ = -Infinity;
        for (let i = 0; i < numPoints; i++) {
            const z = pointsData.positions[i * 3 + 2];
            if (z < minZ) minZ = z;
            if (z > maxZ) maxZ = z;
        }
        const range = (maxZ - minZ) || 1.0;

        for (let i = 0; i < numPoints; i++) {
            const z = pointsData.positions[i * 3 + 2];
            const norm = (z - minZ) / range;
            // Hot-cold colormap (blue to cyan to green to yellow to red)
            const c = getColormapColor(norm);
            colors[i * 3] = c.r;
            colors[i * 3 + 1] = c.g;
            colors[i * 3 + 2] = c.b;
        }
    }
    else if (activeColorMode === COLOR_MODE.DEPTH && activeCameraId !== "free") {
        // Color by distance to active camera
        const cam = datasetConfig.cameras.find(c => c.id == activeCameraId);
        if (cam) {
            const cx = cam.position.x;
            const cy = cam.position.y;
            const cz = cam.position.z;

            let minD = Infinity, maxD = -Infinity;
            const dists = new Float32Array(numPoints);
            for (let i = 0; i < numPoints; i++) {
                const dx = pointsData.positions[i * 3] - cx;
                const dy = pointsData.positions[i * 3 + 1] - cy;
                const dz = pointsData.positions[i * 3 + 2] - cz;
                const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
                dists[i] = d;
                if (d < minD) minD = d;
                if (d > maxD) maxD = d;
            }
            const range = (maxD - minD) || 1.0;

            for (let i = 0; i < numPoints; i++) {
                const norm = (dists[i] - minD) / range;
                const c = getColormapColor(1.0 - norm); // Closer is red/warm
                colors[i * 3] = c.r;
                colors[i * 3 + 1] = c.g;
                colors[i * 3 + 2] = c.b;
            }
        } else {
            colors.fill(1.0); // fallback
        }
    }
    else {
        // Solid color mode
        for (let i = 0; i < numPoints; i++) {
            colors[i * 3] = solidPointColor.r;
            colors[i * 3 + 1] = solidPointColor.g;
            colors[i * 3 + 2] = solidPointColor.b;
        }
    }

    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
}

function getColormapColor(val) {
    // Val from 0 to 1
    // Blue (0) -> Cyan (0.25) -> Green (0.5) -> Yellow (0.75) -> Red (1.0)
    const color = new THREE.Color();
    if (val < 0.25) {
        const t = val / 0.25;
        color.setRGB(0, t, 1);
    } else if (val < 0.5) {
        const t = (val - 0.25) / 0.25;
        color.setRGB(0, 1, 1 - t);
    } else if (val < 0.75) {
        const t = (val - 0.5) / 0.25;
        color.setRGB(t, 1, 0);
    } else {
        const t = (val - 0.75) / 0.25;
        color.setRGB(1, 1 - t, 0);
    }
    return color;
}

// --- CAMERA FRUSTUMS GENERATION ---
function buildCameraFrustums(cameras) {
    // Clear old helpers
    cameraHelpers.forEach(mesh => scene.remove(mesh));
    cameraHelpers = [];

    if (!cameras || cameras.length === 0) return;

    cameras.forEach(cam => {
        const C = cam.position;
        const F = cam.forward;
        const R = cam.right;
        const U = cam.up;

        // Size scale for the frustum representation
        const scale = 25.0;

        // Camera axes coordinates relative to CamPosition:
        // Tip: (0,0,0)
        // Base corners:
        // Top-Right: F + R*w + U*h
        // Top-Left: F - R*w + U*h
        // Bottom-Right: F + R*w - U*h
        // Bottom-Left: F - R*w - U*h
        // Assuming FOV is 90 deg, horizontal half-width is 1.0, vertical is ResY/ResX (e.g. 1080/1920 = 0.5625)
        const aspect = (activeDataset.toLowerCase() === 'fountain') ? 2048 / 3072 : 1080 / 1920;
        const w = 1.0;
        const h = aspect;

        const pTip = new THREE.Vector3(C.x, C.y, C.z);

        const fVec = new THREE.Vector3(F.x, F.y, F.z).multiplyScalar(scale);
        const rVec = new THREE.Vector3(R.x, R.y, R.z).multiplyScalar(scale * w);
        const uVec = new THREE.Vector3(U.x, U.y, U.z).multiplyScalar(scale * h);

        const tr = pTip.clone().add(fVec).add(rVec).add(uVec);
        const tl = pTip.clone().add(fVec).sub(rVec).add(uVec);
        const br = pTip.clone().add(fVec).add(rVec).sub(uVec);
        const bl = pTip.clone().add(fVec).sub(rVec).sub(uVec);

        const points = [
            pTip, tr, pTip, tl, pTip, br, pTip, bl, // rays from camera center
            tr, tl, tl, bl, bl, br, br, tr         // base frame
        ];

        const geom = new THREE.BufferGeometry().setFromPoints(points);

        // Green lines for cameras, red for the currently selected one
        const color = 0x3fb950;
        const mat = new THREE.LineBasicMaterial({
            color: color,
            linewidth: 2,
            transparent: true,
            opacity: 0.7
        });

        const line = new THREE.LineSegments(geom, mat);
        line.userData = { cameraId: cam.id };
        scene.add(line);
        cameraHelpers.push(line);
    });
}

function updateCameraHelpersHighlighting() {
    cameraHelpers.forEach(helper => {
        const id = helper.userData.cameraId;
        if (id == activeCameraId) {
            helper.material.color.setHex(0xff3e83); // Accent pink
            helper.material.opacity = 1.0;
        } else {
            helper.material.color.setHex(0x3fb950); // Accent green
            helper.material.opacity = 0.6;
        }
    });
}

// --- ALIGN CAMERA TO POSE ---
function alignCameraToPose() {
    if (activeCameraId === "free") {
        camera.up.set(0, 0, 1);
        controls.enabled = true;
        controls.update();
        document.getElementById('lock-view-toggle').disabled = true;
        document.getElementById('lock-view-toggle').checked = false;
        document.getElementById('image-overlay').style.opacity = 0;
        document.getElementById('image-opacity').value = 0;
        document.getElementById('opacity-val').textContent = 0;
        document.getElementById('camera-badge').textContent = "Free Orbit";
        document.getElementById('camera-badge').className = "badge";
        return;
    }

    const cam = datasetConfig.cameras.find(c => c.id == activeCameraId);
    if (!cam) return;

    // Automatically lock the camera view when a camera is selected
    // so OrbitControls does not immediately overwrite the camera's orientation
    document.getElementById('lock-view-toggle').checked = true;
    controls.enabled = false;
    document.getElementById('lock-view-toggle').disabled = false;
    document.getElementById('camera-badge').textContent = `Camera ${cam.id}`;
    document.getElementById('camera-badge').className = "badge warning";

    const C = cam.position;
    const F = cam.forward;
    const R = cam.right;
    const U = cam.up;

    // Set OrbitControls target along the forward vector
    // so that if they later unlock orbit, the camera doesn't jump
    const targetDistance = 300;
    controls.target.set(
        C.x + F.x * targetDistance,
        C.y + F.y * targetDistance,
        C.z + F.z * targetDistance
    );

    // camera.up remains (0, 0, 1) globally, so OrbitControls behaves correctly on unlock

    // Construct rotation matrix (Right-handed camera frame)
    // local X = CamRight
    // local Y = CamUp
    // local Z = -CamForward
    const matrix = new THREE.Matrix4();
    matrix.set(
        R.x, U.x, -F.x, C.x,
        R.y, U.y, -F.y, C.y,
        R.z, U.z, -F.z, C.z,
        0, 0, 0, 1
    );

    // Apply translation and rotation to Three.js camera
    matrix.decompose(camera.position, camera.quaternion, camera.scale);
    camera.updateMatrix();
    camera.updateMatrixWorld(true);

    // Calculate vertical FOV from horizontal FOV or intrinsic matrix K
    const ResX = datasetConfig.cameras.length > 0 ? (activeDataset.toLowerCase() === 'fountain' ? 3072 : 1920) : 1920;
    const ResY = datasetConfig.cameras.length > 0 ? (activeDataset.toLowerCase() === 'fountain' ? 2048 : 1080) : 1080;

    if (activeK) {
        // Vertical FOV = 2 * arctan(cy / fy)
        const vFovRad = 2 * Math.atan(activeK.cy / activeK.fy);
        camera.fov = vFovRad * (180.0 / Math.PI);
    } else {
        // Default horizontal FOV = 90 deg
        const hFovRad = 90.0 * (Math.PI / 180.0);
        const vFovRad = 2 * Math.atan(Math.tan(hFovRad / 2.0) * (ResY / ResX));
        camera.fov = vFovRad * (180.0 / Math.PI);
    }

    camera.aspect = ResX / ResY;
    camera.updateProjectionMatrix();


    // Update overlay image
    const overlay = document.getElementById('image-overlay');
    const ext = datasetConfig.cameras.length > 0 ? (activeDataset.toLowerCase() === 'fountain' ? 'jpg' : 'png') : 'png';
    const prefix = activeDataset.toLowerCase();

    // Formulate image filename (e.g. box1.png, entrance2.png, fountain1.jpg, statue3.png)
    const filename = `${prefix}${cam.id}.${ext}`;
    const loader = document.getElementById('image-loading-indicator');
    loader.classList.remove('hidden');

    overlay.src = `/images/${activeDataset}/${filename}`;
    overlay.onload = () => {
        loader.classList.add('hidden');
        const opacityVal = document.getElementById('image-opacity').value;
        overlay.style.opacity = opacityVal / 100;
    };
    overlay.onerror = () => {
        loader.classList.add('hidden');
        console.error("Failed to load overlay image:", overlay.src);
    };
}

// --- SYNTHETIC POINT GENERATOR ---
function generateSyntheticPrimitive() {
    if (syntheticPoints) {
        scene.remove(syntheticPoints);
        syntheticPoints = null;
    }

    if (!syntheticParams.show) {
        document.getElementById('synth-count').textContent = "0 (hidden)";
        return;
    }

    const shape = syntheticParams.shape;
    const tx = syntheticParams.tx;
    const ty = syntheticParams.ty;
    const tz = syntheticParams.tz;
    const rx = syntheticParams.rx * (Math.PI / 180.0);
    const ry = syntheticParams.ry * (Math.PI / 180.0);
    const rz = syntheticParams.rz * (Math.PI / 180.0);
    const w = syntheticParams.w;
    const h = syntheticParams.h;
    const d = syntheticParams.d;
    const N = syntheticParams.density;

    let pts = [];
    let cols = [];

    const Euler = new THREE.Euler(rx, ry, rz);

    if (shape === 'cube') {
        // Generate faces of a cube
        // We divide the faces of the cube of sizes (w, h, d)
        // 6 faces:
        // Front (+Z) & Back (-Z)
        // Right (+X) & Left (-X)
        // Top (+Y) & Bottom (-Y)
        const checkSquares = 8.0; // 8x8 checkerboard pattern

        const generateFace = (sizeU, sizeV, offsetW, axis) => {
            const halfU = sizeU / 2.0;
            const halfV = sizeV / 2.0;
            const stepU = sizeU / N;
            const stepV = sizeV / N;

            for (let i = 0; i <= N; i++) {
                const u = i * stepU - halfU;
                for (let j = 0; j <= N; j++) {
                    const v = j * stepV - halfV;

                    let pLocal;
                    if (axis === 'z') {
                        pLocal = new THREE.Vector3(u, v, offsetW);
                    } else if (axis === 'x') {
                        pLocal = new THREE.Vector3(offsetW, u, v);
                    } else { // 'y'
                        pLocal = new THREE.Vector3(u, offsetW, v);
                    }

                    // Rotate and Translate
                    pLocal.applyEuler(Euler);
                    pLocal.add(new THREE.Vector3(tx, ty, tz));

                    pts.push(pLocal.x, pLocal.y, pLocal.z);

                    // Color: checkerboard pattern
                    const uIdx = Math.floor((u + halfU) / (sizeU / checkSquares));
                    const vIdx = Math.floor((v + halfV) / (sizeV / checkSquares));
                    const isWhite = (uIdx + vIdx) % 2 === 0;

                    const r = isWhite ? 0.95 : 0.15;
                    const g = isWhite ? 0.95 : 0.15;
                    const b = isWhite ? 0.95 : 0.15;

                    cols.push(r, g, b);
                }
            }
        };

        generateFace(w, h, d / 2, 'z');    // Front
        generateFace(w, h, -d / 2, 'z');   // Back
        generateFace(h, d, w / 2, 'x');    // Right
        generateFace(h, d, -w / 2, 'x');   // Left
        generateFace(w, d, h / 2, 'y');    // Top
        generateFace(w, d, -h / 2, 'y');   // Bottom

    } else if (shape === 'grid') {
        // Dense 3D Point Grid
        const stepX = w / Math.min(N, 20);
        const stepY = h / Math.min(N, 20);
        const stepZ = d / Math.min(N, 20);

        for (let x = -w / 2; x <= w / 2; x += stepX) {
            for (let y = -h / 2; y <= h / 2; y += stepY) {
                for (let z = -d / 2; z <= d / 2; z += stepZ) {
                    const pLocal = new THREE.Vector3(x, y, z);
                    pLocal.applyEuler(Euler);
                    pLocal.add(new THREE.Vector3(tx, ty, tz));
                    pts.push(pLocal.x, pLocal.y, pLocal.z);

                    // Rainbow color by coordinates
                    cols.push(
                        (x + w / 2) / w,
                        (y + h / 2) / h,
                        (z + d / 2) / d
                    );
                }
            }
        }
    } else if (shape === 'sphere') {
        // Dense sphere points
        const radius = w / 2;
        for (let i = 0; i < N; i++) {
            const phi = Math.acos(-1 + (2 * i) / N);
            const theta = Math.sqrt(N * Math.PI) * phi;

            const x = radius * Math.sin(phi) * Math.cos(theta);
            const y = radius * Math.sin(phi) * Math.sin(theta);
            const z = radius * Math.cos(phi);

            const pLocal = new THREE.Vector3(x, y, z);
            pLocal.applyEuler(Euler);
            pLocal.add(new THREE.Vector3(tx, ty, tz));

            pts.push(pLocal.x, pLocal.y, pLocal.z);

            // Color by sphere normal
            cols.push(
                (x / radius) * 0.5 + 0.5,
                (y / radius) * 0.5 + 0.5,
                (z / radius) * 0.5 + 0.5
            );
        }
    }

    syntheticPointsData.positions = new Float32Array(pts);
    syntheticPointsData.colors = new Float32Array(cols);

    document.getElementById('synth-count').textContent = (pts.length / 3).toLocaleString();

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(syntheticPointsData.positions, 3));

    // Apply colors based on active color mode
    applyColorsAttribute(geometry, syntheticPointsData, true);

    const size = parseFloat(document.getElementById('point-size').value) * 1.2; // slightly larger for visibility
    const material = new THREE.PointsMaterial({
        size: size,
        vertexColors: true,
        sizeAttenuation: true,
        transparent: true,
        opacity: 0.95
    });

    syntheticPoints = new THREE.Points(geometry, material);
    scene.add(syntheticPoints);
}

// --- APPLY MATRIX TRANSFORMATION TO POINTS ---
function updatePointCloudObjectTransform() {
    if (!pointCloud) return;

    const tx = pointCloudTransform.tx;
    const ty = pointCloudTransform.ty;
    const tz = pointCloudTransform.tz;
    const rx = pointCloudTransform.rx * (Math.PI / 180.0);
    const ry = pointCloudTransform.ry * (Math.PI / 180.0);
    const rz = pointCloudTransform.rz * (Math.PI / 180.0);
    const scale = pointCloudTransform.scale;

    pointCloud.position.set(tx, ty, tz);
    pointCloud.rotation.set(rx, ry, rz);
    pointCloud.scale.set(scale, scale, scale);
}

function resetPointCloudTransforms() {
    pointCloudTransform = { tx: 0, ty: 0, tz: 0, rx: 0, ry: 0, rz: 0, scale: 1.0 };

    document.getElementById('trans-x').value = 0; document.getElementById('tx-val').textContent = 0;
    document.getElementById('trans-y').value = 0; document.getElementById('ty-val').textContent = 0;
    document.getElementById('trans-z').value = 0; document.getElementById('tz-val').textContent = 0;

    document.getElementById('rot-x').value = 0; document.getElementById('rx-val').textContent = 0;
    document.getElementById('rot-y').value = 0; document.getElementById('ry-val').textContent = 0;
    document.getElementById('rot-z').value = 0; document.getElementById('rz-val').textContent = 0;

    document.getElementById('scale-all').value = 1.0; document.getElementById('scale-val').textContent = 1.0;

    updatePointCloudObjectTransform();
}

// --- EXPORT TO CSV CORNER ---
function exportAlignedPointsToCSV() {
    let finalPositions = [];
    let finalColors = [];

    // 1. Get transformed loaded point cloud
    if (pointCloud && loadedPointsData.positions) {
        pointCloud.updateMatrixWorld(true);
        const matrix = pointCloud.matrixWorld;

        const numPoints = loadedPointsData.positions.length / 3;
        for (let i = 0; i < numPoints; i++) {
            const v = new THREE.Vector3(
                loadedPointsData.positions[i * 3],
                loadedPointsData.positions[i * 3 + 1],
                loadedPointsData.positions[i * 3 + 2]
            );
            v.applyMatrix4(matrix);

            finalPositions.push(v.x, v.y, v.z);

            // Retrieve active colors from the mesh attribute
            const colorAttr = pointCloud.geometry.getAttribute('color');
            if (colorAttr) {
                finalColors.push(
                    Math.round(colorAttr.getX(i) * 255),
                    Math.round(colorAttr.getY(i) * 255),
                    Math.round(colorAttr.getZ(i) * 255)
                );
            } else {
                finalColors.push(255, 255, 255);
            }
        }
    }

    // 2. Add synthetic points if visible
    if (syntheticPoints && syntheticPointsData.positions && syntheticParams.show) {
        const numPoints = syntheticPointsData.positions.length / 3;
        for (let i = 0; i < numPoints; i++) {
            finalPositions.push(
                syntheticPointsData.positions[i * 3],
                syntheticPointsData.positions[i * 3 + 1],
                syntheticPointsData.positions[i * 3 + 2]
            );

            const colorAttr = syntheticPoints.geometry.getAttribute('color');
            if (colorAttr) {
                finalColors.push(
                    Math.round(colorAttr.getX(i) * 255),
                    Math.round(colorAttr.getY(i) * 255),
                    Math.round(colorAttr.getZ(i) * 255)
                );
            } else {
                finalColors.push(255, 255, 255);
            }
        }
    }

    if (finalPositions.length === 0) {
        alert("No point cloud data available to export.");
        return;
    }

    // Generate CSV content
    let csvContent = "X,Y,Z,R,G,B\n";
    const numFinalPoints = finalPositions.length / 3;
    for (let i = 0; i < numFinalPoints; i++) {
        const x = finalPositions[i * 3].toFixed(4);
        const y = finalPositions[i * 3 + 1].toFixed(4);
        const z = finalPositions[i * 3 + 2].toFixed(4);
        const r = finalColors[i * 3];
        const g = finalColors[i * 3 + 1];
        const b = finalColors[i * 3 + 2];
        csvContent += `${x},${y},${z},${r},${g},${b}\n`;
    }

    // Download CSV trigger
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    const filename = `${activeDataset || 'scene'}_aligned_points.csv`;

    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, filename);
    } else {
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// --- CUSTOM CSV FILE UPLOADER ---
function handleCustomCSVUpload(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
        const text = e.target.result;
        const lines = text.split('\n');

        let pts = [];
        let cols = [];
        let hasHeader = false;
        let colMap = { x: 0, y: 1, z: 2, r: -1, g: -1, b: -1 };

        if (lines.length === 0) return;

        // Parse header
        const firstLine = lines[0].trim();
        if (firstLine.toLowerCase().includes('x') || firstLine.toLowerCase().includes('y')) {
            hasHeader = true;
            const headers = firstLine.split(/[,;\t]/).map(h => h.trim().toLowerCase());
            colMap.x = headers.indexOf('x');
            colMap.y = headers.indexOf('y');
            colMap.z = headers.indexOf('z');
            colMap.r = headers.indexOf('r');
            if (colMap.r === -1) colMap.r = headers.indexOf('red');
            colMap.g = headers.indexOf('g');
            if (colMap.g === -1) colMap.g = headers.indexOf('green');
            colMap.b = headers.indexOf('b');
            if (colMap.b === -1) colMap.b = headers.indexOf('blue');
        }

        const startIdx = hasHeader ? 1 : 0;
        for (let i = startIdx; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            const parts = line.split(/[,;\t]/);
            if (parts.length < 3) continue;

            try {
                const x = parseFloat(parts[colMap.x]);
                const y = parseFloat(parts[colMap.y]);
                const z = parseFloat(parts[colMap.z]);

                let r = 1.0, g = 1.0, b = 1.0;
                if (colMap.r !== -1 && colMap.g !== -1 && colMap.b !== -1) {
                    r = parseFloat(parts[colMap.r]) / (parts[colMap.r].includes('.') ? 1.0 : 255.0);
                    g = parseFloat(parts[colMap.g]) / (parts[colMap.g].includes('.') ? 1.0 : 255.0);
                    b = parseFloat(parts[colMap.b]) / (parts[colMap.b].includes('.') ? 1.0 : 255.0);
                }

                pts.push(x, y, z);
                cols.push(r, g, b);
            } catch (err) {
                // skip line on error
            }
        }

        basePointsData.positions = new Float32Array(pts);
        basePointsData.colors = new Float32Array(cols);

        resetPointCloudTransforms();
        applyFilters();
        alert(`Successfully imported point cloud with ${pts.length / 3} points!`);
    };
    reader.readAsText(file);
}

// --- UI EVENT HANDLERS BINDING ---
function setupUIEventHandlers() {
    // Dataset switch
    document.getElementById('dataset-select').addEventListener('change', (e) => {
        loadDataset(e.target.value);
    });

    // Camera switches
    document.getElementById('camera-select').addEventListener('change', (e) => {
        activeCameraId = e.target.value;
        updateCameraHelpersHighlighting();
        alignCameraToPose();
    });

    document.getElementById('prev-cam-btn').addEventListener('click', () => {
        const select = document.getElementById('camera-select');
        const currentIndex = select.selectedIndex;
        if (currentIndex > 0) {
            select.selectedIndex = currentIndex - 1;
            select.dispatchEvent(new Event('change'));
        }
    });

    document.getElementById('next-cam-btn').addEventListener('click', () => {
        const select = document.getElementById('camera-select');
        const currentIndex = select.selectedIndex;
        if (currentIndex < select.options.length - 1) {
            select.selectedIndex = currentIndex + 1;
            select.dispatchEvent(new Event('change'));
        }
    });

    // Lock controls toggle
    const lockToggle = document.getElementById('lock-view-toggle');
    lockToggle.addEventListener('change', () => {
        controls.enabled = !lockToggle.checked;
        if (controls.enabled) {
            // Synchronize OrbitControls target with camera's current state to prevent jumping
            const C = camera.position;
            const F = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
            controls.target.copy(C).addScaledVector(F, 300);
            controls.update();
        }
    });

    // --- POINT CLOUD FILTERS EVENTS ---
    // Z-Height Cut
    document.getElementById('filter-z-enable').addEventListener('change', (e) => {
        filtersState.zHeightEnabled = e.target.checked;
        document.getElementById('card-filter-z').classList.toggle('active', e.target.checked);
        applyFilters();
    });
    
    document.getElementById('filter-z-min').addEventListener('input', (e) => {
        filtersState.minZ = parseFloat(e.target.value);
        document.getElementById('filter-z-min-val').textContent = filtersState.minZ;
        if (filtersState.zHeightEnabled) applyFilters();
    });
    
    document.getElementById('filter-z-max').addEventListener('input', (e) => {
        filtersState.maxZ = parseFloat(e.target.value);
        document.getElementById('filter-z-max-val').textContent = filtersState.maxZ;
        if (filtersState.zHeightEnabled) applyFilters();
    });

    // Radius Outlier Removal (ROR)
    document.getElementById('filter-ror-enable').addEventListener('change', (e) => {
        filtersState.rorEnabled = e.target.checked;
        document.getElementById('card-filter-ror').classList.toggle('active', e.target.checked);
        applyFilters();
    });
    
    document.getElementById('filter-ror-rad').addEventListener('input', (e) => {
        filtersState.rorRadius = parseFloat(e.target.value);
        document.getElementById('filter-ror-rad-val').textContent = filtersState.rorRadius.toFixed(1);
        if (filtersState.rorEnabled) applyFilters();
    });
    
    document.getElementById('filter-ror-n').addEventListener('input', (e) => {
        filtersState.rorMinNeighbors = parseInt(e.target.value);
        document.getElementById('filter-ror-n-val').textContent = filtersState.rorMinNeighbors;
        if (filtersState.rorEnabled) applyFilters();
    });

    // Statistical Outlier Removal (SOR)
    document.getElementById('filter-sor-enable').addEventListener('change', (e) => {
        filtersState.sorEnabled = e.target.checked;
        document.getElementById('card-filter-sor').classList.toggle('active', e.target.checked);
        applyFilters();
    });
    
    document.getElementById('filter-sor-k').addEventListener('input', (e) => {
        filtersState.sorNeighbors = parseInt(e.target.value);
        document.getElementById('filter-sor-k-val').textContent = filtersState.sorNeighbors;
        if (filtersState.sorEnabled) applyFilters();
    });
    
    document.getElementById('filter-sor-ratio').addEventListener('input', (e) => {
        filtersState.sorStdRatio = parseFloat(e.target.value);
        document.getElementById('filter-sor-ratio-val').textContent = filtersState.sorStdRatio.toFixed(1);
        if (filtersState.sorEnabled) applyFilters();
    });

    // Local Surface Interpolation
    document.getElementById('filter-interp-enable').addEventListener('change', (e) => {
        filtersState.interpolateEnabled = e.target.checked;
        document.getElementById('card-filter-interp').classList.toggle('active', e.target.checked);
        applyFilters();
    });
    
    document.getElementById('filter-interp-k').addEventListener('input', (e) => {
        filtersState.interpolateK = parseInt(e.target.value);
        document.getElementById('filter-interp-k-val').textContent = filtersState.interpolateK;
        if (filtersState.interpolateEnabled) applyFilters();
    });
    
    document.getElementById('filter-interp-min').addEventListener('input', (e) => {
        filtersState.interpolateMinDist = parseFloat(e.target.value);
        document.getElementById('filter-interp-min-val').textContent = filtersState.interpolateMinDist.toFixed(1);
        if (filtersState.interpolateEnabled) applyFilters();
    });
    
    document.getElementById('filter-interp-max').addEventListener('input', (e) => {
        filtersState.interpolateMaxDist = parseFloat(e.target.value);
        document.getElementById('filter-interp-max-val').textContent = filtersState.interpolateMaxDist.toFixed(1);
        if (filtersState.interpolateEnabled) applyFilters();
    });

    // Camera view opacity
    const opacitySlider = document.getElementById('image-opacity');
    opacitySlider.addEventListener('input', (e) => {
        const val = e.target.value;
        document.getElementById('opacity-val').textContent = val;
        document.getElementById('image-overlay').style.opacity = val / 100;
    });

    // Frustums toggle
    document.getElementById('frustum-toggle').addEventListener('change', (e) => {
        cameraHelpers.forEach(helper => helper.visible = e.target.checked);
    });

    // Grid / Axes Toggles
    document.getElementById('grid-toggle').addEventListener('change', (e) => {
        const obj = scene.getObjectByName('grid-helper');
        if (obj) obj.visible = e.target.checked;
    });

    document.getElementById('axes-toggle').addEventListener('change', (e) => {
        const obj = scene.getObjectByName('axes-helper');
        if (obj) obj.visible = e.target.checked;
    });

    // Point Size Slider
    document.getElementById('point-size').addEventListener('input', (e) => {
        const size = parseFloat(e.target.value);
        document.getElementById('size-val').textContent = size;
        if (pointCloud) pointCloud.material.size = size;
        if (syntheticPoints) syntheticPoints.material.size = size * 1.2;
    });

    // Color Mode Select
    document.getElementById('color-mode').addEventListener('change', (e) => {
        activeColorMode = e.target.value;

        // Show/hide solid color picker
        const pickerGrp = document.getElementById('solid-color-group');
        if (activeColorMode === COLOR_MODE.SOLID) {
            pickerGrp.style.display = 'block';
        } else {
            pickerGrp.style.display = 'none';
        }

        // Reapply colors
        if (pointCloud && loadedPointsData.positions) {
            applyColorsAttribute(pointCloud.geometry, loadedPointsData, false);
            pointCloud.geometry.getAttribute('color').needsUpdate = true;
        }
        if (syntheticPoints && syntheticPointsData.positions) {
            applyColorsAttribute(syntheticPoints.geometry, syntheticPointsData, true);
            syntheticPoints.geometry.getAttribute('color').needsUpdate = true;
        }
    });

    // Solid color picker
    document.getElementById('solid-color-picker').addEventListener('input', (e) => {
        solidPointColor.set(e.target.value);
        if (activeColorMode === COLOR_MODE.SOLID) {
            if (pointCloud) {
                applyColorsAttribute(pointCloud.geometry, loadedPointsData, false);
                pointCloud.geometry.getAttribute('color').needsUpdate = true;
            }
            if (syntheticPoints) {
                applyColorsAttribute(syntheticPoints.geometry, syntheticPointsData, true);
                syntheticPoints.geometry.getAttribute('color').needsUpdate = true;
            }
        }
    });

    // Interactive Alignment Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });

    // Sidebar Slide Events for Point Cloud Transforms
    const transSliders = ['trans-x', 'trans-y', 'trans-z', 'rot-x', 'rot-y', 'rot-z', 'scale-all'];
    transSliders.forEach(id => {
        document.getElementById(id).addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            const shortId = id.replace('trans-', 't').replace('rot-', 'r').replace('-all', '');
            pointCloudTransform[shortId] = val;
            document.getElementById(`${shortId}-val`).textContent = val;

            updatePointCloudObjectTransform();
        });
    });

    // 90-degree step buttons for rotation
    document.querySelectorAll('.step-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const axis = btn.dataset.axis; // "rx", "ry", "rz"
            const step = parseFloat(btn.dataset.step); // 90 or -90
            let currentVal = pointCloudTransform[axis] || 0;
            let newVal = currentVal + step;
            
            // Wrap rotation between -180 and 180
            if (newVal > 180) newVal -= 360;
            if (newVal < -180) newVal += 360;
            
            pointCloudTransform[axis] = newVal;
            document.getElementById(`${axis}-val`).textContent = newVal;
            
            // Update the slider element position
            const sliderId = axis === 'rx' ? 'rot-x' : (axis === 'ry' ? 'rot-y' : 'rot-z');
            document.getElementById(sliderId).value = newVal;
            
            updatePointCloudObjectTransform();
        });
    });

    document.getElementById('reset-transform-btn').addEventListener('click', resetPointCloudTransforms);

    // Sidebar Slide Events for Synthetic Primitive
    const synthSliders = ['s-trans-x', 's-trans-y', 's-trans-z', 's-dim-w', 's-dim-h', 's-dim-d', 's-rot-x', 's-rot-y', 's-rot-z'];
    synthSliders.forEach(id => {
        document.getElementById(id).addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            const paramKey = id.substring(2).replace('trans-', 't').replace('rot-', 'r').replace('dim-', '');
            syntheticParams[paramKey] = val;
            document.getElementById(`${id}-val`).textContent = val;

            generateSyntheticPrimitive();
        });
    });

    // Shape primitive changer
    document.getElementById('synth-shape').addEventListener('change', (e) => {
        syntheticParams.shape = e.target.value;
        const wLabel = document.querySelector('label[for="s-dim-w"]') || document.getElementById('s-dim-w').previousElementSibling;

        // Hide/Show height & depth controls depending on shape
        if (syntheticParams.shape === 'sphere') {
            document.getElementById('dim-h-group').style.display = 'none';
            document.getElementById('dim-d-group').style.display = 'none';
            if (wLabel) wLabel.childNodes[0].textContent = "Radius: ";
        } else {
            document.getElementById('dim-h-group').style.display = 'block';
            document.getElementById('dim-d-group').style.display = 'block';
            if (wLabel) wLabel.childNodes[0].textContent = "W: ";
        }

        generateSyntheticPrimitive();
    });

    // Density Changer
    document.getElementById('synth-density').addEventListener('change', (e) => {
        syntheticParams.density = parseInt(e.target.value) || 20;
        generateSyntheticPrimitive();
    });

    // Show toggle
    document.getElementById('synth-show').addEventListener('change', (e) => {
        syntheticParams.show = e.target.checked;
        generateSyntheticPrimitive();
    });

    // Data Actions
    document.getElementById('upload-csv-btn').addEventListener('click', () => {
        document.getElementById('csv-file-loader').click();
    });

    document.getElementById('csv-file-loader').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleCustomCSVUpload(e.target.files[0]);
        }
    });

    document.getElementById('export-csv-btn').addEventListener('click', exportAlignedPointsToCSV);
}

// --- MAIN LOOP ---
function animate() {
    requestAnimationFrame(animate);

    if (controls && controls.enabled) {
        controls.update();
    }

    // Update active viewport details card with camera stats
    updateCameraDetailsCard();

    renderer.render(scene, camera);
}

function updateCameraDetailsCard() {
    const pos = camera.position;
    document.getElementById('cam-pos-xyz').textContent = `X: ${pos.x.toFixed(2)} Y: ${pos.y.toFixed(2)} Z: ${pos.z.toFixed(2)}`;

    // Vector calculations: forward, right, up vectors in world coordinates
    const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
    const rgt = new THREE.Vector3(-1, 0, 0).applyQuaternion(camera.quaternion);
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);

    document.getElementById('cam-fwd-xyz').textContent = `X: ${fwd.x.toFixed(3)} Y: ${fwd.y.toFixed(3)} Z: ${fwd.z.toFixed(3)}`;
    document.getElementById('cam-rgt-xyz').textContent = `X: ${rgt.x.toFixed(3)} Y: ${rgt.y.toFixed(3)} Z: ${rgt.z.toFixed(3)}`;
    document.getElementById('cam-up-xyz').textContent = `X: ${up.x.toFixed(3)} Y: ${up.y.toFixed(3)} Z: ${up.z.toFixed(3)}`;

    // Intrinsic matrix display
    if (activeK) {
        document.getElementById('intrinsics-row').style.display = 'flex';
        document.getElementById('cam-k-matrix').textContent = `fx: ${activeK.fx.toFixed(1)} fy: ${activeK.fy.toFixed(1)} cx: ${activeK.cx.toFixed(1)} cy: ${activeK.cy.toFixed(1)}`;
    } else {
        // Assume default K based on 90 deg horizontal FOV
        const ResX = activeDataset && activeDataset.toLowerCase() === 'fountain' ? 3072 : 1920;
        const ResY = activeDataset && activeDataset.toLowerCase() === 'fountain' ? 2048 : 1080;
        const fx = ResX / 2.0;
        const fy = ResX / 2.0;
        const cx = ResX / 2.0;
        const cy = ResY / 2.0;
        document.getElementById('intrinsics-row').style.display = 'flex';
        document.getElementById('cam-k-matrix').textContent = `fx: ${fx.toFixed(1)} fy: ${fy.toFixed(1)} cx: ${cx.toFixed(1)} cy: ${cy.toFixed(1)} (calculated)`;
    }
}

// --- INTERACTIVE POINT CLOUD FILTERS IMPLEMENTATION ---

function initFilterDefaults(datasetName) {
    const name = datasetName.toLowerCase();
    
    // Z limits
    let minZ = -300;
    let maxZ = 600;
    
    if (name === 'box') {
        minZ = -200;
        maxZ = 424;
        
        filtersState.rorRadius = 15.0;
        filtersState.rorMinNeighbors = 3;
        filtersState.sorNeighbors = 16;
        filtersState.sorStdRatio = 1.2;
        filtersState.interpolateMinDist = 8.0;
        filtersState.interpolateMaxDist = 35.0;
    } else if (name === 'entrance') {
        minZ = -200;
        maxZ = 500;
        
        filtersState.rorRadius = 25.0;
        filtersState.rorMinNeighbors = 4;
        filtersState.sorNeighbors = 16;
        filtersState.sorStdRatio = 1.2;
        filtersState.interpolateMinDist = 12.0;
        filtersState.interpolateMaxDist = 45.0;
    } else if (name === 'fountain') {
        minZ = -100;
        maxZ = 800;
        
        filtersState.rorRadius = 10.0;
        filtersState.rorMinNeighbors = 3;
        filtersState.sorNeighbors = 16;
        filtersState.sorStdRatio = 1.2;
        filtersState.interpolateMinDist = 8.0;
        filtersState.interpolateMaxDist = 30.0;
    } else if (name === 'statue') {
        minZ = -200;
        maxZ = 600;
        
        filtersState.rorRadius = 12.0;
        filtersState.rorMinNeighbors = 3;
        filtersState.sorNeighbors = 16;
        filtersState.sorStdRatio = 1.2;
        filtersState.interpolateMinDist = 8.0;
        filtersState.interpolateMaxDist = 30.0;
    }
    
    // Set UI elements value and text
    document.getElementById('filter-z-min').value = minZ;
    document.getElementById('filter-z-min-val').textContent = minZ;
    document.getElementById('filter-z-max').value = maxZ;
    document.getElementById('filter-z-max-val').textContent = maxZ;
    
    document.getElementById('filter-ror-rad').value = filtersState.rorRadius;
    document.getElementById('filter-ror-rad-val').textContent = filtersState.rorRadius.toFixed(1);
    document.getElementById('filter-ror-n').value = filtersState.rorMinNeighbors;
    document.getElementById('filter-ror-n-val').textContent = filtersState.rorMinNeighbors;
    
    document.getElementById('filter-sor-k').value = filtersState.sorNeighbors;
    document.getElementById('filter-sor-k-val').textContent = filtersState.sorNeighbors;
    document.getElementById('filter-sor-ratio').value = filtersState.sorStdRatio;
    document.getElementById('filter-sor-ratio-val').textContent = filtersState.sorStdRatio.toFixed(1);
    
    document.getElementById('filter-interp-k').value = filtersState.interpolateK;
    document.getElementById('filter-interp-k-val').textContent = filtersState.interpolateK;
    document.getElementById('filter-interp-min').value = filtersState.interpolateMinDist;
    document.getElementById('filter-interp-min-val').textContent = filtersState.interpolateMinDist.toFixed(1);
    document.getElementById('filter-interp-max').value = filtersState.interpolateMaxDist;
    document.getElementById('filter-interp-max-val').textContent = filtersState.interpolateMaxDist.toFixed(1);
    
    // Uncheck enabling checkboxes by default
    document.getElementById('filter-z-enable').checked = false;
    document.getElementById('filter-ror-enable').checked = false;
    document.getElementById('filter-sor-enable').checked = false;
    document.getElementById('filter-interp-enable').checked = false;
    
    // Remove active styling from cards
    document.querySelectorAll('.filter-card').forEach(c => c.classList.remove('active'));
    
    filtersState.zHeightEnabled = false;
    filtersState.rorEnabled = false;
    filtersState.sorEnabled = false;
    filtersState.interpolateEnabled = false;
    
    filtersState.minZ = minZ;
    filtersState.maxZ = maxZ;
}

function applyFilters() {
    if (!basePointsData.positions || basePointsData.positions.length === 0) return;

    let positions = basePointsData.positions;
    let colors = basePointsData.colors;
    
    // 1. Z-Height / Passthrough Filter
    if (filtersState.zHeightEnabled) {
        const minZ = filtersState.minZ;
        const maxZ = filtersState.maxZ;
        
        let keepIndices = [];
        const numPoints = positions.length / 3;
        for (let i = 0; i < numPoints; i++) {
            const z = positions[i * 3 + 2];
            if (z >= minZ && z <= maxZ) {
                keepIndices.push(i);
            }
        }
        
        const newPos = new Float32Array(keepIndices.length * 3);
        const newColors = new Float32Array(keepIndices.length * 3);
        for (let i = 0; i < keepIndices.length; i++) {
            const idx = keepIndices[i];
            newPos[i * 3] = positions[idx * 3];
            newPos[i * 3 + 1] = positions[idx * 3 + 1];
            newPos[i * 3 + 2] = positions[idx * 3 + 2];
            
            newColors[i * 3] = colors[idx * 3];
            newColors[i * 3 + 1] = colors[idx * 3 + 1];
            newColors[i * 3 + 2] = colors[idx * 3 + 2];
        }
        positions = newPos;
        colors = newColors;
    }
    
    // 2. Radius Outlier Removal (ROR) Filter
    if (filtersState.rorEnabled && positions.length > 0) {
        const filtered = applyRORFilterJS(positions, colors, filtersState.rorRadius, filtersState.rorMinNeighbors);
        positions = filtered.positions;
        colors = filtered.colors;
    }

    // 3. Statistical Outlier Removal (SOR) Filter
    if (filtersState.sorEnabled && positions.length > 0) {
        const filtered = applySORFilterJS(positions, colors, filtersState.sorNeighbors, filtersState.sorStdRatio);
        positions = filtered.positions;
        colors = filtered.colors;
    }

    // 4. Local Surface Interpolation Filter
    if (filtersState.interpolateEnabled && positions.length > 0) {
        const interpolated = applyInterpolationJS(positions, colors, filtersState.interpolateK, filtersState.interpolateMinDist, filtersState.interpolateMaxDist);
        positions = interpolated.positions;
        colors = interpolated.colors;
    }

    loadedPointsData.positions = positions;
    loadedPointsData.colors = colors;

    document.getElementById('points-count').textContent = (positions.length / 3).toLocaleString();
    
    // Re-render Point Cloud mesh in Three.js viewport
    renderPointsMesh();
}

function applyRORFilterJS(positions, colors, radius, minNeighbors) {
    const numPoints = positions.length / 3;
    const voxelSize = radius;
    const grid = {};
    
    // Build grid
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        const key = `${vx},${vy},${vz}`;
        
        if (!grid[key]) grid[key] = [];
        grid[key].push(i);
    }
    
    const keepIndices = [];
    const r2 = radius * radius;
    
    // Query grid
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        
        let count = 0;
        
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                for (let dz = -1; dz <= 1; dz++) {
                    const key = `${vx + dx},${vy + dy},${vz + dz}`;
                    const pts = grid[key];
                    if (pts) {
                        for (let j = 0; j < pts.length; j++) {
                            const idx = pts[j];
                            const px = positions[idx * 3];
                            const py = positions[idx * 3 + 1];
                            const pz = positions[idx * 3 + 2];
                            
                            const dist2 = (x - px) * (x - px) + (y - py) * (y - py) + (z - pz) * (z - pz);
                            if (dist2 <= r2) {
                                count++;
                            }
                        }
                    }
                }
            }
        }
        
        if (count >= minNeighbors) {
            keepIndices.push(i);
        }
    }
    
    const newPos = new Float32Array(keepIndices.length * 3);
    const newColors = new Float32Array(keepIndices.length * 3);
    for (let i = 0; i < keepIndices.length; i++) {
        const idx = keepIndices[i];
        newPos[i * 3] = positions[idx * 3];
        newPos[i * 3 + 1] = positions[idx * 3 + 1];
        newPos[i * 3 + 2] = positions[idx * 3 + 2];
        
        newColors[i * 3] = colors[idx * 3];
        newColors[i * 3 + 1] = colors[idx * 3 + 1];
        newColors[i * 3 + 2] = colors[idx * 3 + 2];
    }
    
    return { positions: newPos, colors: newColors };
}

function applySORFilterJS(positions, colors, k, stdRatio) {
    const numPoints = positions.length / 3;
    const voxelSize = 35.0; // search voxel size
    const grid = {};
    
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        const key = `${vx},${vy},${vz}`;
        if (!grid[key]) grid[key] = [];
        grid[key].push(i);
    }
    
    const meanDists = new Float32Array(numPoints);
    
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        
        const candidates = [];
        
        // Layer 1 search (3x3x3 voxels)
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                for (let dz = -1; dz <= 1; dz++) {
                    const key = `${vx + dx},${vy + dy},${vz + dz}`;
                    const pts = grid[key];
                    if (pts) {
                        for (let j = 0; j < pts.length; j++) {
                            const idx = pts[j];
                            if (idx === i) continue;
                            const px = positions[idx * 3];
                            const py = positions[idx * 3 + 1];
                            const pz = positions[idx * 3 + 2];
                            const dist2 = (x - px) * (x - px) + (y - py) * (y - py) + (z - pz) * (z - pz);
                            candidates.push(Math.sqrt(dist2));
                        }
                    }
                }
            }
        }
        
        // Layer 2 search if not enough candidates (5x5x5 voxels)
        if (candidates.length < k) {
            for (let dx = -2; dx <= 2; dx++) {
                for (let dy = -2; dy <= 2; dy++) {
                    for (let dz = -2; dz <= 2; dz++) {
                        if (Math.abs(dx) <= 1 && Math.abs(dy) <= 1 && Math.abs(dz) <= 1) continue;
                        const key = `${vx + dx},${vy + dy},${vz + dz}`;
                        const pts = grid[key];
                        if (pts) {
                            for (let j = 0; j < pts.length; j++) {
                                const idx = pts[j];
                                if (idx === i) continue;
                                const px = positions[idx * 3];
                                const py = positions[idx * 3 + 1];
                                const pz = positions[idx * 3 + 2];
                                const dist2 = (x - px) * (x - px) + (y - py) * (y - py) + (z - pz) * (z - pz);
                                candidates.push(Math.sqrt(dist2));
                            }
                        }
                    }
                }
            }
        }
        
        if (candidates.length === 0) {
            meanDists[i] = 9999.0;
            continue;
        }
        
        candidates.sort((a, b) => a - b);
        const count = Math.min(k, candidates.length);
        let sum = 0;
        for (let j = 0; j < count; j++) {
            sum += candidates[j];
        }
        meanDists[i] = sum / count;
    }
    
    // Calculate global statistics
    let globalSum = 0;
    let validCount = 0;
    for (let i = 0; i < numPoints; i++) {
        if (meanDists[i] < 9990.0) {
            globalSum += meanDists[i];
            validCount++;
        }
    }
    const globalMean = globalSum / (validCount || 1);
    
    let sumSqDiff = 0;
    for (let i = 0; i < numPoints; i++) {
        if (meanDists[i] < 9990.0) {
            const diff = meanDists[i] - globalMean;
            sumSqDiff += diff * diff;
        }
    }
    const globalStd = Math.sqrt(sumSqDiff / (validCount || 1));
    const threshold = globalMean + stdRatio * globalStd;
    
    const keepIndices = [];
    for (let i = 0; i < numPoints; i++) {
        if (meanDists[i] <= threshold) {
            keepIndices.push(i);
        }
    }
    
    const newPos = new Float32Array(keepIndices.length * 3);
    const newColors = new Float32Array(keepIndices.length * 3);
    for (let i = 0; i < keepIndices.length; i++) {
        const idx = keepIndices[i];
        newPos[i * 3] = positions[idx * 3];
        newPos[i * 3 + 1] = positions[idx * 3 + 1];
        newPos[i * 3 + 2] = positions[idx * 3 + 2];
        newColors[i * 3] = colors[idx * 3];
        newColors[i * 3 + 1] = colors[idx * 3 + 1];
        newColors[i * 3 + 2] = colors[idx * 3 + 2];
    }
    
    return { positions: newPos, colors: newColors };
}

function applyInterpolationJS(positions, colors, k, minDist, maxDist) {
    const numPoints = positions.length / 3;
    const voxelSize = maxDist;
    const grid = {};
    
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        const key = `${vx},${vy},${vz}`;
        if (!grid[key]) grid[key] = [];
        grid[key].push(i);
    }
    
    const newPts = [];
    const newClrs = [];
    
    for (let i = 0; i < numPoints; i++) {
        const x = positions[i * 3];
        const y = positions[i * 3 + 1];
        const z = positions[i * 3 + 2];
        const vx = Math.floor(x / voxelSize);
        const vy = Math.floor(y / voxelSize);
        const vz = Math.floor(z / voxelSize);
        
        const candidates = [];
        
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                for (let dz = -1; dz <= 1; dz++) {
                    const key = `${vx + dx},${vy + dy},${vz + dz}`;
                    const pts = grid[key];
                    if (pts) {
                        for (let j = 0; j < pts.length; j++) {
                            const idx = pts[j];
                            if (idx <= i) continue;
                            const px = positions[idx * 3];
                            const py = positions[idx * 3 + 1];
                            const pz = positions[idx * 3 + 2];
                            const dist2 = (x - px) * (x - px) + (y - py) * (y - py) + (z - pz) * (z - pz);
                            const dist = Math.sqrt(dist2);
                            if (dist > minDist && dist < maxDist) {
                                candidates.push({ idx, dist });
                            }
                        }
                    }
                }
            }
        }
        
        candidates.sort((a, b) => a.dist - b.dist);
        const count = Math.min(k, candidates.length);
        
        for (let c = 0; c < count; c++) {
            const neighborIdx = candidates[c].idx;
            const d = candidates[c].dist;
            
            const px = positions[neighborIdx * 3];
            const py = positions[neighborIdx * 3 + 1];
            const pz = positions[neighborIdx * 3 + 2];
            
            const cr = colors[i * 3];
            const cg = colors[i * 3 + 1];
            const cb = colors[i * 3 + 2];
            
            const ncr = colors[neighborIdx * 3];
            const ncg = colors[neighborIdx * 3 + 1];
            const ncb = colors[neighborIdx * 3 + 2];
            
            const steps = Math.floor(d / minDist);
            for (let m = 1; m <= steps; m++) {
                const t = m / (steps + 1);
                const rx = (Math.random() - 0.5) * 0.15;
                const ry = (Math.random() - 0.5) * 0.15;
                const rz = (Math.random() - 0.5) * 0.15;
                
                newPts.push(
                    (1 - t) * x + t * px + rx,
                    (1 - t) * y + t * py + ry,
                    (1 - t) * z + t * pz + rz
                );
                
                newClrs.push(
                    (1 - t) * cr + t * ncr,
                    (1 - t) * cg + t * ncg,
                    (1 - t) * cb + t * ncb
                );
            }
        }
    }
    
    const combinedLength = positions.length + newPts.length;
    const combinedPos = new Float32Array(combinedLength);
    const combinedColors = new Float32Array(combinedLength);
    
    combinedPos.set(positions);
    combinedColors.set(colors);
    
    for (let i = 0; i < newPts.length; i++) {
        combinedPos[positions.length + i] = newPts[i];
        combinedColors[colors.length + i] = newClrs[i];
    }
    
    return { positions: combinedPos, colors: combinedColors };
}
