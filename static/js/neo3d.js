// neo3d.js
// expects endpoint /api/neo/today to return simplified structure like in your Flask app

(async function(){
  // --- Helpers ---
  const container = document.getElementById('canvas-container');
  const infoPanel = document.getElementById('info');
  const infoTitle = document.getElementById('info-title');
  const infoBody = document.getElementById('info-body');
  const infoClose = document.getElementById('info-close');
  const reloadBtn = document.getElementById('reloadBtn');
  const scaleInput = document.getElementById('scaleDist');
  const speedInput = document.getElementById('timeSpeed');

  infoClose.onclick = ()=> infoPanel.classList.add('hidden');

  // three.js scene
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x02061a, 0.0008);

  const renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x02061a, 1);
  container.appendChild(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 1, 2e7);
  camera.position.set(0, 2000000, 6000000);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 30000;
  controls.maxDistance = 1e8;

  window.addEventListener('resize', ()=>{
    camera.aspect = window.innerWidth/window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  // Lighting
  const dir = new THREE.DirectionalLight(0xffffff, 1.0);
  dir.position.set(1000000, 0, 0);
  scene.add(dir);
  scene.add(new THREE.AmbientLight(0x204050, 0.8));

  // Earth (simple textured sphere)
  const earthRadiusKm = 6371; // actual km
  // we'll define scale: 1 unit = scaleFactor km
  let scaleFactor = Number(scaleInput.value); // user adjustable

  const earthGeo = new THREE.SphereGeometry(earthRadiusKm / scaleFactor, 64, 32);
  const earthMat = new THREE.MeshPhongMaterial({
    color: 0x2a4b7a,
    emissive: 0x051427,
    shininess: 10,
    specular: 0x111111,
    flatShading: false
  });
  const earthMesh = new THREE.Mesh(earthGeo, earthMat);
  scene.add(earthMesh);

  // add a subtle atmospheric glow
  const atmosphereGeo = new THREE.SphereGeometry(earthRadiusKm / scaleFactor * 1.03, 32, 16);
  const atmosphereMat = new THREE.MeshBasicMaterial({
    color: 0x6fb8ff,
    transparent: true,
    opacity: 0.06
  });
  const atmosphere = new THREE.Mesh(atmosphereGeo, atmosphereMat);
  scene.add(atmosphere);

  // helper group for NEOs
  const neoGroup = new THREE.Group();
  scene.add(neoGroup);

  // scale and speed reactive
  scaleInput.addEventListener('input', ()=>{
    scaleFactor = Number(scaleInput.value);
    // update earth scale
    earthMesh.scale.setScalar((6371/scaleFactor) / earthMesh.geometry.parameters.radius);
    atmosphere.scale.setScalar((6371/scaleFactor*1.03) / atmosphere.geometry.parameters.radius);
    // reposition camera if needed
  });

  // Data structures
  let neos = []; // array of { data, mesh, pathLine, progress, vectorStart, vectorEnd, speedKmPerS }
  let globalTimeSpeed = Number(speedInput.value);

  speedInput.addEventListener('input', ()=>{ globalTimeSpeed = Number(speedInput.value); });

  // Convert kilometers => three.js units (units = km / scaleFactor)
  function kmToUnits(km){ return km / scaleFactor; }

  // Create a small sphere for a NEO
  function createNeoMesh(radiusKm, hazardous){
    // clamp radius for visibility: radius ~ (diameter_m/2)/scaleFactor but minimum
    const r = Math.max( Math.log10(Math.max(radiusKm, 0.5)) * 0.75, 0.6 );
    const geo = new THREE.SphereGeometry(r, 10, 8);
    const mat = new THREE.MeshStandardMaterial({
      color: hazardous ? 0xff6b6b : 0x7be0ff,
      roughness: 0.8,
      metalness: 0.1,
    });
    return new THREE.Mesh(geo, mat);
  }

  // Create curved trail (simple straight line or gentle curve) as geometry
  function createTrail(start, end){
    const points = [];
    const steps = 64;
    for(let i=0;i<=steps;i++){
      const t = i/steps;
      // slight curve near earth (sin)
      const curveFactor = Math.sin(t*Math.PI) * (Math.max(0.02, 0.02));
      const x = start.x*(1-t) + end.x*t + curveFactor*start.y;
      const y = start.y*(1-t) + end.y*t + curveFactor*start.z;
      const z = start.z*(1-t) + end.z*t + curveFactor*start.x;
      points.push(new THREE.Vector3(x,y,z));
    }
    const curveGeo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({linewidth:1, opacity:0.6, transparent:true, color:0xffffff});
    return new THREE.Line(curveGeo, mat);
  }

  // Raycaster for clicks
  const ray = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  renderer.domElement.addEventListener('pointerdown', (ev)=>{
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    ray.setFromCamera(mouse, camera);
    const intersects = ray.intersectObjects(neoGroup.children, true);
    if(intersects.length){
      const obj = intersects[0].object;
      if(obj.userData && obj.userData.neo){
        showInfo(obj.userData.neo);
      }
    }
  });

  function showInfo(neo){
    infoTitle.textContent = neo.name || neo.id || 'NEO';
    const orbit = neo.orbit || {};
    infoBody.innerHTML = `
      <div>Diameter: ${neo.diameter ? Math.round(neo.diameter) + ' m' : 'Unknown'}</div>
      <div>Semi-major axis: ${orbit.semi_major_axis ? orbit.semi_major_axis.toFixed(3) + ' AU' : 'N/A'}</div>
      <div>Eccentricity: ${orbit.eccentricity ? orbit.eccentricity.toFixed(4) : 'N/A'}</div>
      <div>Inclination: ${orbit.inclination ? orbit.inclination.toFixed(2) + '°' : 'N/A'}</div>
      <div>Potentially hazardous: ${neo.is_hazardous ? 'Yes' : 'No'}</div>
      <div style="margin-top:8px"><a href="https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=${encodeURIComponent(neo.id || neo.name)}" target="_blank">More (JPL)</a></div>
    `;
    infoPanel.classList.remove('hidden');
  }

  // Load data and build objects
  async function loadData(){
    // Clear existing
    while(neoGroup.children.length) neoGroup.remove(neoGroup.children[0]);
    neos = [];

    document.body.style.cursor = 'wait';
    try{
      const res = await fetch('/asteroids');
      if(!res.ok) throw new Error('Asteroids API failed: '+res.status);
      const neoObj = await res.json();
      // iterate
      neoObj.forEach((n,i)=>{
        // For orbital data visualization, we don't have close approach data
        // Instead we'll use orbital parameters to create realistic orbits
        const orbit = n.orbit || {};
        
        // Use orbital velocity approximation: v ≈ sqrt(μ/a) where μ = GM_sun, a = semi_major_axis
        // For simplicity, use average orbital speed
        const semiMajorAU = orbit.semi_major_axis || 1.5; // AU
        const v_kms = Math.sqrt(30 / semiMajorAU); // rough orbital speed in km/s
        
        // Miss distance: use orbital distance at closest approach (perihelion)
        const eccentricity = orbit.eccentricity || 0.1;
        const perihelionAU = semiMajorAU * (1 - eccentricity);
        const missKm = perihelionAU * 149597871; // AU to km
        
        // size: use diameter provided
        const sizeMeters = n.diameter || 100; // meters
        const sizeKm = sizeMeters / 1000.0;

        // approach vector: choose random direction (unit vector) but aim to pass at 'missKm' distance.
        // We'll create start and end points where path crosses near-Earth with asymptotic straight-line path.
        // Choose a random azimuth/inclination
        const az = Math.random() * Math.PI * 2;
        const inc = (Math.random() - 0.5) * Math.PI / 3; // +/- 60 deg
        // unit direction
        const dir = new THREE.Vector3(Math.cos(az)*Math.cos(inc), Math.sin(inc), Math.sin(az)*Math.cos(inc)).normalize();

        // compute closest approach point: choose a point at distance 'missKm' from earth center perpendicular to direction
        // vector from Earth center to closest approach = perpendicular to dir with magnitude missKm
        // pick arbitrary perpendicular vector using cross with an arbitrary vector
        let perp = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0.3, 0.7, 0.2));
        if(perp.length() < 0.01) perp = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0.9, 0.1, 0.05));
        perp.normalize();

        const closestPoint = perp.clone().multiplyScalar(missKm / scaleFactor); // in scene units

        // choose start point far away along -dir, and end point far away along +dir
        const travelDist = Math.max( (missKm * 12), 500000); // total travel range (km) before/after
        const startKm = -travelDist;
        const endKm = travelDist;

        const start = dir.clone().multiplyScalar(startKm / scaleFactor).add(closestPoint);
        const end = dir.clone().multiplyScalar(endKm / scaleFactor).add(closestPoint);

        // mesh
        const mesh = createNeoMesh(sizeKm, n.is_hazardous);
        // initial position at some fraction along path (randomize initial position so they aren't all at same spot)
        const initialT = Math.random() * 0.8 + 0.1; // 0.1..0.9
        const startV = start.clone();
        const endV = end.clone();
        const pos = startV.clone().lerp(endV, initialT);
        mesh.position.copy(pos);
        mesh.userData = { neo: n };

        // trail
        const trail = createTrail(startV, endV);
        trail.material.color = new THREE.Color(n.is_hazardous ? 0xff6b6b : 0x7be0ff);
        trail.material.opacity = 0.18;

        // store
        neoGroup.add(trail);
        neoGroup.add(mesh);
        neos.push({
          data: n,
          mesh,
          trail,
          start: startV,
          end: endV,
          progress: initialT,
          // speed in units per second = (v_kms km/s) / scaleFactor
          speedUnitsPerSecond: (v_kms / scaleFactor) || (25 / scaleFactor),
          v_kms: v_kms,
          missKm: missKm,
        });
      });

      console.log('NEOs loaded', neos.length);
    }catch(e){
      console.error('Failed to load NEOs:', e);
      alert('Failed to load NEO data. See console.');
    }finally{
      document.body.style.cursor = 'default';
    }
  }

  // animate
  const clock = new THREE.Clock();
  function animate(){
    requestAnimationFrame(animate);
    const dt = clock.getDelta() * globalTimeSpeed; // scale time
    // update NEO positions
    for(const n of neos){
      // progress moves from 0 -> 1 over some duration based on speed relative to travel distance
      // compute path length:
      const pathLenUnits = n.start.distanceTo(n.end); // units
      // speedUnitsPerSecond already in units/sec
      const dProgress = (n.speedUnitsPerSecond * dt) / pathLenUnits;
      n.progress += dProgress;
      if(n.progress > 1.02) {
        // loop: reset to before start
        n.progress = -0.02 + Math.random()*0.08;
      }
      // interpolate position
      const p = n.start.clone().lerp(n.end, n.progress);
      n.mesh.position.copy(p);
    }

    // slight rotation for Earth to feel alive
    earthMesh.rotation.y += 0.0008 * globalTimeSpeed;
    atmosphere.rotation.y += 0.0009 * globalTimeSpeed;

    controls.update();
    renderer.render(scene, camera);
  }

  // reload button
  reloadBtn.addEventListener('click', ()=> loadData());

  // kick off
  await loadData();
  animate();

})();

