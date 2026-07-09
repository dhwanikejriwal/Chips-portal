// ===================== Aadhaar CG Dashboard — map + interactivity =====================

// ---- clock ----
function tickClock(){
  const d = new Date();
  document.getElementById('clock').textContent = d.toLocaleTimeString('en-IN',{hour12:false}) + ' IST';
}
tickClock();
setInterval(tickClock, 1000);

// ---- derive state-level aggregates ----
const districtNames = CG_GEOJSON.features.map(f => f.properties.dist_name);
const totalPop = districtNames.reduce((s,n)=> s + DISTRICT_METRICS[n].population, 0);
const totalEnrolled = districtNames.reduce((s,n)=> s + DISTRICT_METRICS[n].enrolled, 0);
const avgSaturation = (totalEnrolled/totalPop*100);
const totalUpdates = districtNames.reduce((s,n)=> s + DISTRICT_METRICS[n].monthly_updates, 0);
const totalCenters = districtNames.reduce((s,n)=> s + DISTRICT_METRICS[n].enrollment_centers, 0);
const avgRejection = (districtNames.reduce((s,n)=> s + DISTRICT_METRICS[n].rejection_rate, 0)/districtNames.length);

function fmt(n){ return n.toLocaleString('en-IN'); }

const statCards = [
  {label:'Total Population (Aadhaar-eligible)', value: fmt(totalPop), sub:'across 33 districts', cls:''},
  {label:'Aadhaar Enrolled', value: fmt(totalEnrolled), sub:`${avgSaturation.toFixed(1)}% state saturation`, cls:'up'},
  {label:'Enrollment Centres', value: fmt(totalCenters), sub:'active across state', cls:''},
  {label:'Monthly Update Requests', value: fmt(totalUpdates), sub:'demographic + biometric', cls:''},
  {label:'Avg. Rejection Rate', value: avgRejection.toFixed(1)+'%', sub: avgRejection>2 ? 'above target' : 'within target', cls: avgRejection>2 ? 'warn':'up'},
];

const stripEl = document.getElementById('stateStrip');
stripEl.innerHTML = statCards.map(c => `
  <div class="stat-card">
    <div class="stat-label">${c.label}</div>
    <div class="stat-value">${c.value}</div>
    <div class="stat-sub ${c.cls}">${c.sub}</div>
  </div>
`).join('');

// ---- metric config ----
const METRICS = {
  saturation:      { label:'Aadhaar Saturation %', fmt: v=>v.toFixed(1)+'%', accessor: n=>DISTRICT_METRICS[n].saturation },
  enrolled:        { label:'Total Enrolled',        fmt: v=>fmt(Math.round(v)), accessor: n=>DISTRICT_METRICS[n].enrolled },
  monthly_updates: { label:'Updates / month',        fmt: v=>fmt(Math.round(v)), accessor: n=>DISTRICT_METRICS[n].monthly_updates },
  rejection_rate:  { label:'Rejection Rate %',       fmt: v=>v.toFixed(1)+'%', accessor: n=>DISTRICT_METRICS[n].rejection_rate }
};

let currentMetric = 'saturation';

// ---- D3 projection fitted to CG only ----
const svg = d3.select('#map-svg');
const width = 760, height = 640;
const projection = d3.geoMercator().fitExtent([[24,20],[width-24,height-20]], CG_GEOJSON);
const path = d3.geoPath().projection(projection);

const g = svg.append('g').attr('id','districts-g');
const labelG = svg.append('g').attr('id','labels-g');

let colorScale;

function buildColorScale(){
  const vals = districtNames.map(n => METRICS[currentMetric].accessor(n));
  const [min,max] = d3.extent(vals);
  colorScale = d3.scaleLinear()
    .domain([min, (min+max)/2, max])
    .range(['#16313f', '#1f7a73', '#2dd4bf']);
  document.getElementById('legendLow').textContent = METRICS[currentMetric].fmt(min);
  document.getElementById('legendHigh').textContent = METRICS[currentMetric].fmt(max);
}
buildColorScale();

const tooltip = document.getElementById('tooltip');
let lockedDistrict = null;

const paths = g.selectAll('path')
  .data(CG_GEOJSON.features)
  .join('path')
  .attr('class','district-path')
  .attr('d', path)
  .attr('fill', f => colorScale(METRICS[currentMetric].accessor(f.properties.dist_name)))
  .on('mousemove', (event, f) => showTooltip(event, f))
  .on('mouseleave', () => { tooltip.style.opacity = 0; })
  .on('click', (event, f) => selectDistrict(f.properties.dist_name));

// small centroid labels (only shown for larger districts to avoid clutter)
labelG.selectAll('text')
  .data(CG_GEOJSON.features)
  .join('text')
  .attr('class','district-label')
  .attr('transform', f => {
    const c = path.centroid(f);
    return `translate(${c[0]},${c[1]})`;
  })
  .text(f => f.properties.dist_name.length <= 10 ? f.properties.dist_name : '');

function showTooltip(event, f){
  const n = f.properties.dist_name;
  const m = DISTRICT_METRICS[n];
  tooltip.innerHTML = `
    <div class="t-name">${n}</div>
    <div class="t-row"><span>Saturation</span><b>${m.saturation.toFixed(1)}%</b></div>
    <div class="t-row"><span>Enrolled</span><b>${fmt(m.enrolled)}</b></div>
    <div class="t-row"><span>Updates/mo</span><b>${fmt(m.monthly_updates)}</b></div>
    <div class="t-row"><span>Rejection</span><b>${m.rejection_rate.toFixed(1)}%</b></div>
  `;
  tooltip.style.left = (event.clientX + 16) + 'px';
  tooltip.style.top = (event.clientY - 10) + 'px';
  tooltip.style.opacity = 1;
}

function refreshColors(){
  buildColorScale();
  paths.attr('fill', f => colorScale(METRICS[currentMetric].accessor(f.properties.dist_name)));
}

document.querySelectorAll('#metricToggle button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#metricToggle button').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    currentMetric = btn.dataset.metric;
    document.getElementById('panelMeta').textContent =
      `33 districts · shaded by ${METRICS[currentMetric].label} · click a district for full profile`;
    refreshColors();
  });
});

// ---- detail panel ----
function rankOf(name, key, higherIsBetter=true){
  const sorted = districtNames.slice().sort((a,b)=> higherIsBetter
    ? DISTRICT_METRICS[b][key]-DISTRICT_METRICS[a][key]
    : DISTRICT_METRICS[a][key]-DISTRICT_METRICS[b][key]);
  return sorted.indexOf(name)+1;
}

function selectDistrict(name){
  lockedDistrict = name;
  paths.classed('active', f => f.properties.dist_name === name);
  const f = CG_GEOJSON.features.find(f => f.properties.dist_name === name);
  const m = DISTRICT_METRICS[name];
  const satRank = rankOf(name,'saturation', true);
  const maxBar = Math.max(...districtNames.map(n=>DISTRICT_METRICS[n].population));

  document.getElementById('detailPanel').innerHTML = `
    <div class="detail-header">
      <div class="eyebrow">District Profile</div>
      <h2>${name}</h2>
      <div class="hi-name">${f.properties.dist_name_hi || ''}</div>
      <div class="detail-codes">
        <span>Dist Code <b>${f.properties.dist_code}</b></span>
        <span>Division <b>${f.properties.div_code}</b></span>
        <span>State <b>CG-${f.properties.state_code}</b></span>
      </div>
    </div>

    <div class="metric-grid">
      <div class="m-box"><div class="m-label">Population</div><div class="m-value">${fmt(m.population)}</div></div>
      <div class="m-box"><div class="m-label">Enrolled</div><div class="m-value good">${fmt(m.enrolled)}</div></div>
      <div class="m-box"><div class="m-label">Saturation</div><div class="m-value ${m.saturation>97?'good':m.saturation>93?'warn':'bad'}">${m.saturation.toFixed(1)}%</div></div>
      <div class="m-box"><div class="m-label">Rejection Rate</div><div class="m-value ${m.rejection_rate<1.5?'good':m.rejection_rate<3?'warn':'bad'}">${m.rejection_rate.toFixed(1)}%</div></div>
      <div class="m-box"><div class="m-label">Child (5–17) Saturation</div><div class="m-value">${m.child_saturation_5_17.toFixed(1)}%</div></div>
      <div class="m-box"><div class="m-label">Enrollment Centres</div><div class="m-value">${m.enrollment_centers}</div></div>
    </div>

    <div class="bar-row">
      <div class="b-top"><span>Overall Saturation</span><b>${m.saturation.toFixed(1)}%</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:${m.saturation}%"></div></div>
    </div>
    <div class="bar-row">
      <div class="b-top"><span>Child Saturation (5–17 yrs)</span><b>${m.child_saturation_5_17.toFixed(1)}%</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:${m.child_saturation_5_17}%"></div></div>
    </div>
    <div class="bar-row">
      <div class="b-top"><span>Population share of state</span><b>${(m.population/totalPop*100).toFixed(1)}%</b></div>
      <div class="bar-track"><div class="bar-fill" style="width:${(m.population/maxBar*100)}%"></div></div>
    </div>

    <div class="rank-note">
      📍 <span><b style="color:var(--teal)">${name}</b> ranks <b>#${satRank}</b> of 33 districts by Aadhaar saturation, with <b>${fmt(m.monthly_updates)}</b> demographic/biometric update requests processed this month.</span>
    </div>
  `;
}

// click empty space to deselect (optional UX nicety)
svg.on('click', (event) => {
  if (event.target === svg.node()) {
    lockedDistrict = null;
    paths.classed('active', false);
  }
});
