// Small client-side controller to call our backend endpoints and update the UI.

function $(s){return document.querySelector(s)}
function $all(s){return document.querySelectorAll(s)}

const apodSection = $('#apod-section')
const searchSection = $('#search-section')
const neoSection = $('#neo-section')

$('#btn-apod').addEventListener('click', ()=>{ showOnly(apodSection); loadAPOD(); })
$('#btn-search').addEventListener('click', ()=>{ showOnly(searchSection); })
$('#btn-neo').addEventListener('click', ()=>{ showOnly(neoSection); loadNEO(); })

$('#search-go').addEventListener('click', ()=>{ doSearch(); })
$('#search-q').addEventListener('keydown', (e)=>{ if(e.key==='Enter') doSearch(); })

function showOnly(section){
  [apodSection, searchSection, neoSection].forEach(s=>s.classList.add('hidden'));
  section.classList.remove('hidden');
}

async function loadAPOD(){
  $('#apod-loading').textContent = 'loading...';
  $('#apod-content').innerHTML = '';
  try{
    const res = await fetch('/api/apod');
    const data = await res.json();
    $('#apod-loading').textContent = '';
    const html = `
      <div><strong>${data.title || 'APOD'}</strong> <span class="muted">(${data.date || ''})</span></div>
      <div class="muted">${data.explanation ? data.explanation.slice(0,350) + '...' : ''}</div>
      ${data.media_type === 'image' ? `<img src="${data.url}" alt="apod">` : `<div class="muted">Non-image media: <a href="${data.url}" target="_blank">view</a></div>`}
    `;
    $('#apod-content').innerHTML = html;
  }catch(err){
    $('#apod-loading').textContent = 'Error loading APOD';
    console.error(err);
  }
}

async function doSearch(){
  const q = $('#search-q').value.trim() || 'mars';
  $('#search-results').innerHTML = '<div class="muted">Searching...</div>';
  try{
    const res = await fetch(`/api/search_images?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    const grid = $('#search-results');
    if(!data.results || data.results.length===0){
      grid.innerHTML = '<div class="muted">No results.</div>'; return;
    }
    grid.innerHTML = data.results.map(r=>`
      <div class="thumb">
        <img src="${r.href || '/static/img/placeholder.png'}" alt="${r.title || ''}" onerror="this.src='/static/img/placeholder.png'">
        <div style="font-weight:700">${r.title || ''}</div>
        <div class="muted" style="font-size:12px">${r.date_created || ''}</div>
      </div>
    `).join('');
  }catch(err){
    $('#search-results').innerHTML = '<div class="muted">Search failed</div>';
    console.error(err);
  }
}

async function loadNEO(){
  $('#neo-loading').textContent = 'loading...';
  $('#neo-content').innerHTML = '';
  try{
    const res = await fetch('/api/neo/today');
    const data = await res.json();
    $('#neo-loading').textContent = '';
    const todayKey = Object.keys(data.near_earth_objects || {})[0];
    const items = (data.near_earth_objects || {})[todayKey] || [];
    if(items.length===0){
      $('#neo-content').innerHTML = '<div class="muted">No NEOs today.</div>'; return;
    }
    $('#neo-content').innerHTML = items.map(i=>`
      <div class="neo-item">
        <div style="font-weight:700">${i.name}</div>
        <div class="muted">hazardous: ${i.is_potentially_hazardous}</div>
        <div class="muted">est. size: ${Math.round((i.estimated_diameter_m_min||0))}–${Math.round((i.estimated_diameter_m_max||0))} m</div>
      </div>
    `).join('');
  }catch(err){
    $('#neo-loading').textContent = 'Failed to load NEOs';
    console.error(err);
  }
}

// Initialize default view
showOnly(apodSection);
loadAPOD();
