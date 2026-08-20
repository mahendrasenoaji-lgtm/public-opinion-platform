import { useState, useMemo, useEffect } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import {
  Activity, Gauge, GitCompare, Network, Users, Map, TrendingUp,
  FileText, ShieldCheck, ChevronRight, AlertTriangle, ArrowUpRight,
  ArrowDownRight, Minus, Info, Radio,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  SYNTHETIC DATA — demo dataset, tidak mewakili opini publik nyata   */
/* ------------------------------------------------------------------ */

const WEEKS = ["W18", "W19", "W20", "W21", "W22", "W23", "W24", "W25", "W26", "W27", "W28", "W29"];

const trend = WEEKS.map((w, i) => ({
  week: w,
  survey: [74, 73, 75, 72, 71, 70, 69, 68, 67, 68, 68, 68][i],
  social: [58, 57, 55, 52, 50, 47, 44, 43, 40, 39, 41, 41][i],
  media: [63, 62, 62, 60, 59, 58, 56, 55, 54, 54, 55, 55][i],
  poi: [77.1, 76.4, 76.9, 75.2, 74.6, 73.8, 72.9, 72.0, 71.2, 71.6, 72.1, 72.4][i],
}));

const DIMENSIONS = [
  { key: "sentiment", label: "Sentiment", score: 61, weight: 20, src: "social", note: "Agregat sentiment lintas kanal" },
  { key: "approval", label: "Approval", score: 74, weight: 25, src: "survey", note: "Item approval, survei probabilistik" },
  { key: "trust", label: "Trust", score: 68, weight: 25, src: "survey", note: "Indeks kepercayaan institusi" },
  { key: "satisfaction", label: "Satisfaction", score: 71, weight: 12, src: "survey", note: "Kepuasan layanan publik" },
  { key: "issue", label: "Issue Perception", score: 58, weight: 10, src: "media", note: "Persepsi terhadap isu dominan" },
  { key: "confidence", label: "Confidence", score: 66, weight: 8, src: "survey", note: "Keyakinan terhadap arah kebijakan" },
];

const concerns = [
  { issue: "Harga pangan", share: 31, delta: +6.2, sent: -42, momentum: "naik cepat" },
  { issue: "Biaya transportasi", share: 18, delta: +9.4, sent: -37, momentum: "emerging" },
  { issue: "Lapangan kerja", share: 16, delta: +1.1, sent: -21, momentum: "stabil" },
  { issue: "Layanan kesehatan", share: 12, delta: -2.0, sent: +8, momentum: "melandai" },
  { issue: "Pendidikan", share: 11, delta: -0.4, sent: +19, momentum: "stabil" },
  { issue: "Keamanan", share: 7, delta: -1.8, sent: +4, momentum: "melandai" },
];

const narratives = [
  { id: "A", text: "Kebijakan meningkatkan kesejahteraan", vol: 42, mom: +3, sent: +34, origin: "media", pickup: 71 },
  { id: "B", text: "Kebijakan menaikkan biaya hidup", vol: 31, mom: +14, sent: -48, origin: "social", pickup: 58 },
  { id: "C", text: "Komunikasi pemerintah tidak jelas", vol: 19, mom: +9, sent: -29, origin: "social", pickup: 33 },
  { id: "D", text: "Implementasi berjalan bertahap", vol: 8, mom: -2, sent: +11, origin: "media", pickup: 24 },
];

const segments = [
  { name: "Supporters", size: 24, sent: +62, trust: 81, age: "45+", geo: "Jawa non-urban", concern: "Pendidikan", vol: "rendah" },
  { name: "Soft Supporters", size: 21, sent: +18, trust: 63, age: "35–44", geo: "Kota menengah", concern: "Harga pangan", vol: "sedang" },
  { name: "Neutral", size: 17, sent: +2, trust: 54, age: "25–34", geo: "Merata", concern: "Lapangan kerja", vol: "sedang" },
  { name: "Concerned", size: 19, sent: -31, trust: 44, age: "25–34", geo: "Urban Jawa", concern: "Biaya transportasi", vol: "tinggi" },
  { name: "Oppositional", size: 11, sent: -67, trust: 22, age: "18–24", geo: "Urban besar", concern: "Harga pangan", vol: "rendah" },
  { name: "Volatile", size: 8, sent: -6, trust: 47, age: "18–24", geo: "Luar Jawa", concern: "Biaya transportasi", vol: "sangat tinggi" },
];

const provinces = [
  { p: "DKI Jakarta", poi: 64, trust: 59, approval: 66, top: "Biaya transportasi", d: -6.1, n: 840 },
  { p: "Jawa Barat", poi: 69, trust: 65, approval: 71, top: "Harga pangan", d: -4.4, n: 1120 },
  { p: "Jawa Tengah", poi: 75, trust: 72, approval: 79, top: "Harga pangan", d: -1.2, n: 980 },
  { p: "DI Yogyakarta", poi: 76, trust: 71, approval: 82, top: "Pendidikan", d: +1.8, n: 420 },
  { p: "Jawa Timur", poi: 73, trust: 70, approval: 76, top: "Lapangan kerja", d: -2.0, n: 1040 },
  { p: "Banten", poi: 66, trust: 61, approval: 68, top: "Biaya transportasi", d: -5.3, n: 460 },
  { p: "Bali", poi: 78, trust: 74, approval: 80, top: "Pariwisata", d: +0.6, n: 380 },
  { p: "Sumatera Utara", poi: 70, trust: 66, approval: 72, top: "Harga pangan", d: -3.1, n: 620 },
  { p: "Sumatera Selatan", poi: 71, trust: 67, approval: 73, top: "Harga pangan", d: -2.4, n: 440 },
  { p: "Riau", poi: 68, trust: 63, approval: 70, top: "Lapangan kerja", d: -3.9, n: 390 },
  { p: "Kalimantan Timur", poi: 74, trust: 69, approval: 77, top: "Infrastruktur", d: +0.9, n: 350 },
  { p: "Sulawesi Selatan", poi: 72, trust: 68, approval: 74, top: "Layanan kesehatan", d: -1.4, n: 480 },
  { p: "NTB", poi: 67, trust: 62, approval: 69, top: "Harga pangan", d: -4.8, n: 310 },
  { p: "NTT", poi: 65, trust: 60, approval: 67, top: "Akses layanan", d: -2.7, n: 300 },
  { p: "Papua", poi: 61, trust: 55, approval: 63, top: "Akses layanan", d: -1.1, n: 260 },
  { p: "Maluku", poi: 69, trust: 64, approval: 71, top: "Harga pangan", d: -2.2, n: 240 },
];

const timeline = [
  { d: "01 Jun", e: "Pengumuman kebijakan", tag: "event", v: null },
  { d: "03 Jun", e: "Sentiment positif menguat", tag: "signal", v: "+8%" },
  { d: "07 Jun", e: "Narasi negatif mulai terbentuk", tag: "signal", v: "B" },
  { d: "10 Jun", e: "Percakapan opinion leader meningkat", tag: "signal", v: "×3,4" },
  { d: "12 Jun", e: "Pickup media arus utama", tag: "media", v: "142 artikel" },
  { d: "15 Jun", e: "Opinion Index turun", tag: "alert", v: "−7,0" },
];

const forecastBase = [
  { d: "H+0", low: 72.4, exp: 72.4, high: 72.4 },
  { d: "H+1", low: 71.4, exp: 72.1, high: 72.9 },
  { d: "H+3", low: 70.2, exp: 71.6, high: 73.1 },
  { d: "H+7", low: 69.0, exp: 71.2, high: 73.6 },
  { d: "H+14", low: 67.6, exp: 70.9, high: 74.2 },
  { d: "H+30", low: 66.1, exp: 70.5, high: 75.0 },
];

const NAV = [
  { id: "command", label: "Command Center", icon: Radio },
  { id: "index", label: "Opinion Index", icon: Gauge },
  { id: "consistency", label: "Signal Consistency", icon: GitCompare },
  { id: "narrative", label: "Narrative Map", icon: Network },
  { id: "segments", label: "Public Segments", icon: Users },
  { id: "geo", label: "Geographic Map", icon: Map },
  { id: "forecast", label: "Forecast & Simulator", icon: TrendingUp },
  { id: "brief", label: "Executive Brief", icon: FileText },
  { id: "governance", label: "AI Governance", icon: ShieldCheck },
];

const SRC = { survey: "var(--survey)", social: "var(--social)", media: "var(--media)" };
const SRC_LABEL = { survey: "SURVEI", social: "SOSIAL", media: "MEDIA" };

/* ------------------------------------------------------------------ */
/*  PRIMITIVES                                                         */
/* ------------------------------------------------------------------ */

function Provenance({ method, n, ci, confidence, limits }) {
  return (
    <div className="prov">
      <span><b>METODE</b> {method}</span>
      {n && <span><b>n</b> {n}</span>}
      {ci && <span><b>CI 95%</b> {ci}</span>}
      <span><b>CONFIDENCE</b> {confidence}</span>
      <span className="prov-lim"><b>BATASAN</b> {limits}</span>
    </div>
  );
}

function Panel({ title, kicker, right, children, tone }) {
  return (
    <section className={"panel" + (tone === "light" ? " panel-light" : "")}>
      {(title || right) && (
        <header className="panel-head">
          <div>
            {kicker && <div className="kicker">{kicker}</div>}
            {title && <h2 className="panel-title">{title}</h2>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

function Delta({ v, suffix = "" }) {
  const Icon = v > 0 ? ArrowUpRight : v < 0 ? ArrowDownRight : Minus;
  const cls = v > 0 ? "up" : v < 0 ? "down" : "flat";
  return (
    <span className={"delta " + cls}>
      <Icon size={13} strokeWidth={2.5} />
      {v > 0 ? "+" : ""}{v}{suffix}
    </span>
  );
}

function Bar100({ value, color, muted }) {
  return (
    <div className="bar100">
      <div style={{ width: Math.max(0, Math.min(100, value)) + "%", background: color, opacity: muted ? 0.45 : 1 }} />
    </div>
  );
}

function useCountUp(target, run = true) {
  const [v, setV] = useState(run ? 0 : target);
  useEffect(() => {
    if (!run) { setV(target); return; }
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setV(target); return; }
    let raf, t0;
    const step = (t) => {
      if (!t0) t0 = t;
      const p = Math.min(1, (t - t0) / 700);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, run]);
  return v;
}

const chartAxis = { stroke: "#41526B", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" };
const tipStyle = {
  background: "#0D141D", border: "1px solid #22303F", borderRadius: 2,
  fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: "#E6EDF6",
};

/* ------------------------------------------------------------------ */
/*  SIGNATURE: SIGNAL DIVERGENCE BAND                                  */
/* ------------------------------------------------------------------ */

function DivergenceBand({ survey, social, media }) {
  const vals = [survey, social, media];
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const marks = [
    { k: "survey", v: survey, label: "Survei probabilistik" },
    { k: "media", v: media, label: "Narasi media" },
    { k: "social", v: social, label: "Percakapan sosial" },
  ].sort((a, b) => a.v - b.v);

  return (
    <div className="dvg">
      <div className="dvg-head">
        <div>
          <div className="kicker">One opinion — multiple signals</div>
          <h2 className="panel-title">Sinyal opini tidak sepakat</h2>
        </div>
        <div className="dvg-gap">
          <div className="dvg-gap-n">{hi - lo}</div>
          <div className="kicker">poin selisih</div>
        </div>
      </div>

      <div className="dvg-track">
        <div className="dvg-span" style={{ left: lo + "%", width: (hi - lo) + "%" }} />
        {marks.map((m, i) => (
          <div key={m.k} className="dvg-mark" style={{ left: m.v + "%" }}>
            <div className="dvg-stem" style={{ background: SRC[m.k], height: 26 + i * 16 }} />
            <div className="dvg-dot" style={{ background: SRC[m.k] }} />
            <div className="dvg-tag" style={{ bottom: 34 + i * 16, borderColor: SRC[m.k] }}>
              <span style={{ color: SRC[m.k] }}>{SRC_LABEL[m.k]}</span> {m.v}
            </div>
          </div>
        ))}
        <div className="dvg-scale"><span>0</span><span>50</span><span>100</span></div>
      </div>

      <p className="dvg-read">
        Survei menempatkan opini positif di <b>{survey}</b>, percakapan media sosial di <b>{social}</b>.
        Selisih sebesar ini biasanya berkaitan dengan self-selection platform, komposisi demografis pengguna,
        dan waktu pengukuran — bukan indikasi bahwa salah satu angka keliru.
      </p>
      <Provenance
        method="Survei CATI multistage + agregasi API platform"
        n="8.940 responden / 214.6k mention"
        ci="±1,04 pp"
        confidence="Sedang"
        limits="Sosial tidak representatif populasi; tidak dapat dibobot ke populasi nasional"
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  VIEWS                                                              */
/* ------------------------------------------------------------------ */

function CommandCenter() {
  const poi = useCountUp(72.4);
  const stats = [
    { label: "Public Opinion Index", value: poi.toFixed(1), unit: "/100", d: +4.8, big: true },
    { label: "Trust Index", value: "68.2", unit: "/100", d: -2.1 },
    { label: "Approval", value: "74", unit: "%", d: -1.0 },
    { label: "Opinion Risk", value: "43", unit: "/100", d: +11, risk: "Elevated" },
  ];

  return (
    <>
      <div className="stat-row">
        {stats.map((s) => (
          <div key={s.label} className={"stat" + (s.big ? " stat-big" : "")}>
            <div className="kicker">{s.label}</div>
            <div className="stat-v">
              {s.value}<span className="stat-u">{s.unit}</span>
            </div>
            <div className="stat-foot">
              <Delta v={s.d} />
              {s.risk && <span className="pill pill-warn">{s.risk}</span>}
            </div>
          </div>
        ))}
      </div>

      <DivergenceBand survey={68} social={41} media={55} />

      <div className="grid-2">
        <Panel kicker="12 minggu terakhir" title="Pergerakan tiap sinyal">
          <div className="chart">
            <ResponsiveContainer width="100%" height={230}>
              <LineChart data={trend} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke="#1A2532" vertical={false} />
                <XAxis dataKey="week" {...chartAxis} tickLine={false} axisLine={{ stroke: "#1F2B3C" }} />
                <YAxis domain={[30, 85]} {...chartAxis} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tipStyle} cursor={{ stroke: "#2A3A4D" }} />
                <Line type="monotone" dataKey="survey" stroke="#4DA3FF" strokeWidth={2} dot={false} name="Survei" />
                <Line type="monotone" dataKey="media" stroke="#9B8AFB" strokeWidth={2} dot={false} name="Media" />
                <Line type="monotone" dataKey="social" stroke="#FF7A45" strokeWidth={2} dot={false} name="Sosial" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Provenance method="Time-series tertimbang" n="12 gelombang" confidence="Tinggi" limits="Gelombang W22 memakai booster sample" />
        </Panel>

        <Panel kicker="Pangsa perhatian publik" title="Isu yang paling dibicarakan">
          <ul className="issues">
            {concerns.map((c) => (
              <li key={c.issue}>
                <div className="issue-top">
                  <span className="issue-name">{c.issue}</span>
                  <span className="issue-share">{c.share}%</span>
                </div>
                <Bar100 value={c.share * 3} color={c.sent < 0 ? "var(--neg)" : "var(--pos)"} />
                <div className="issue-meta">
                  <Delta v={c.delta} suffix=" pp" />
                  <span>sentiment {c.sent > 0 ? "+" : ""}{c.sent}</span>
                  <span className="dim">{c.momentum}</span>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel kicker="Rangkaian peristiwa" title="Opinion timeline">
          <ol className="tl">
            {timeline.map((t) => (
              <li key={t.d} className={"tl-" + t.tag}>
                <span className="tl-d">{t.d}</span>
                <span className="tl-e">{t.e}</span>
                {t.v && <span className="tl-v">{t.v}</span>}
              </li>
            ))}
          </ol>
          <p className="note">
            <Info size={13} /> Urutan waktu menunjukkan keterkaitan, bukan sebab-akibat. Klaim kausal
            memerlukan desain kuasi-eksperimen yang tersedia di modul Communication Impact.
          </p>
        </Panel>

        <Panel kicker="Perlu ditinjau manusia" title="Peringatan aktif">
          <div className="alerts">
            {[
              { s: "high", t: "Narasi B tumbuh 14 poin dalam 7 hari", d: "Percepatan tertinggi sejak awal periode. Terkonsentrasi di segmen Concerned, urban Jawa." },
              { s: "med", t: "Trust turun sementara Approval bertahan", d: "Pola divergen. Biasanya mendahului koreksi approval pada gelombang berikutnya." },
              { s: "med", t: "192 respons ditandai kualitas rendah", d: "Straight-lining dan waktu pengisian di bawah ambang. Belum dikeluarkan dari analisis." },
              { s: "low", t: "Cakupan sampel NTT di bawah target", d: "Achieved 300 dari target 380. Bobot pasca-stratifikasi diterapkan." },
            ].map((a) => (
              <div key={a.t} className={"alert alert-" + a.s}>
                <AlertTriangle size={15} />
                <div>
                  <div className="alert-t">{a.t}</div>
                  <div className="alert-d">{a.d}</div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}

function IndexView() {
  const [dims, setDims] = useState(DIMENSIONS);
  const totalW = dims.reduce((a, d) => a + d.weight, 0);
  const poi = useMemo(
    () => dims.reduce((a, d) => a + d.score * (d.weight / totalW), 0),
    [dims, totalW]
  );
  const setW = (k, w) => setDims((p) => p.map((d) => (d.key === k ? { ...d, weight: w } : d)));

  return (
    <>
      <Panel kicker="Indeks komposit — bobot dapat dikonfigurasi per proyek" title="Public Opinion Index">
        <div className="poi-wrap">
          <div className="poi-score">
            <div className="poi-n">{poi.toFixed(1)}</div>
            <div className="poi-scale">/ 100</div>
            <div className="poi-meta">
              <div><b>Periode lalu</b> 71.6</div>
              <div><b>Perubahan</b> <Delta v={+((poi - 71.6).toFixed(1))} /></div>
              <div><b>CI 95%</b> ±1,4</div>
              <div><b>Sampel efektif</b> 8.940</div>
            </div>
          </div>
          <div className="poi-dims">
            {dims.map((d) => (
              <div key={d.key} className="dim">
                <div className="dim-head">
                  <span className="dim-src" style={{ background: SRC[d.src] }} />
                  <span className="dim-label">{d.label}</span>
                  <span className="dim-score">{d.score}</span>
                </div>
                <Bar100 value={d.score} color={SRC[d.src]} muted />
                <div className="dim-w">
                  <input
                    type="range" min="0" max="40" value={d.weight}
                    onChange={(e) => setW(d.key, Number(e.target.value))}
                    aria-label={"Bobot " + d.label}
                  />
                  <span className="dim-wv">{((d.weight / totalW) * 100).toFixed(0)}%</span>
                </div>
                <div className="dim-note">{d.note}</div>
              </div>
            ))}
          </div>
        </div>
        <Provenance
          method="Rata-rata tertimbang enam dimensi, dinormalisasi 0–100"
          n="8.940"
          ci="±1,4"
          confidence="Tinggi"
          limits="Dimensi Sentiment bersumber non-probabilistik dan tidak dapat digeneralisasi ke populasi"
        />
      </Panel>

      <Panel kicker="Jejak indeks" title="POI 12 minggu">
        <div className="chart">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trend} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
              <defs>
                <linearGradient id="gpoi" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4DA3FF" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#4DA3FF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1A2532" vertical={false} />
              <XAxis dataKey="week" {...chartAxis} tickLine={false} axisLine={{ stroke: "#1F2B3C" }} />
              <YAxis domain={[65, 80]} {...chartAxis} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tipStyle} />
              <Area type="monotone" dataKey="poi" stroke="#4DA3FF" strokeWidth={2} fill="url(#gpoi)" name="POI" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </>
  );
}

function Consistency() {
  const rows = [
    { k: "survey", v: 68, n: "8.940 responden", m: "Multistage random sampling, CATI", bias: "Cakupan terbatas pada pemilik telepon aktif" },
    { k: "social", v: 41, n: "214.600 mention", m: "API resmi platform, klasifikasi NLP", bias: "Self-selection, skewed usia muda dan urban" },
    { k: "media", v: 55, n: "3.180 artikel", m: "Klasifikasi stance tingkat artikel", bias: "Bergantung pada agenda redaksi, bukan opini pembaca" },
  ];
  return (
    <>
      <Panel kicker="Fitur pembeda utama" title="Tiga sumber, tiga jawaban berbeda">
        <div className="cons">
          {rows.map((r) => (
            <div key={r.k} className="cons-row">
              <div className="cons-label" style={{ color: SRC[r.k] }}>{SRC_LABEL[r.k]}</div>
              <div className="cons-bar">
                <Bar100 value={r.v} color={SRC[r.k]} />
              </div>
              <div className="cons-v">{r.v}<span className="pct">% positif</span></div>
              <div className="cons-n">{r.n}</div>
            </div>
          ))}
        </div>
        <table className="tbl">
          <thead><tr><th>Sumber</th><th>Metode</th><th>Sumber bias utama</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.k}>
                <td style={{ color: SRC[r.k] }}>{SRC_LABEL[r.k]}</td>
                <td>{r.m}</td>
                <td className="dim">{r.bias}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel kicker="Pembacaan AI" title="Mengapa angkanya berbeda">
        <div className="reads">
          {[
            ["Self-selection", "Yang menulis di media sosial adalah yang punya keluhan. Kelompok puas jarang memposting, sehingga sentiment sosial secara sistematis lebih rendah dari survei."],
            ["Komposisi demografis", "Percakapan didominasi usia 18–34 dan wilayah urban. Segmen 45+ yang paling mendukung hampir tidak terwakili."],
            ["Waktu pengukuran", "Gelombang survei ditutup 6 hari sebelum puncak percakapan. Sebagian pergeseran opini belum tertangkap survei."],
            ["Framing media", "Media memberi ruang pada kedua narasi, sehingga stance agregat berada di antara survei dan sosial."],
          ].map(([t, d]) => (
            <div key={t} className="read">
              <div className="read-t">{t}</div>
              <div className="read-d">{d}</div>
            </div>
          ))}
        </div>
        <Provenance
          method="Dekomposisi selisih + perbandingan profil demografis"
          confidence="Sedang"
          limits="Kontribusi tiap faktor adalah estimasi, bukan dekomposisi varians eksak"
        />
      </Panel>
    </>
  );
}

function NarrativeView() {
  const [sel, setSel] = useState(narratives[1]);
  return (
    <div className="grid-2">
      <Panel kicker="Narasi yang beredar" title="Narrative Map">
        <div className="narrs">
          {narratives.map((n) => (
            <button
              key={n.id}
              className={"narr" + (sel.id === n.id ? " narr-on" : "")}
              onClick={() => setSel(n)}
            >
              <div className="narr-head">
                <span className="narr-id">{n.id}</span>
                <span className="narr-t">{n.text}</span>
                <span className="narr-v">{n.vol}%</span>
              </div>
              <Bar100 value={n.vol * 2} color={n.sent < 0 ? "var(--neg)" : "var(--pos)"} />
              <div className="narr-meta">
                <span>momentum <Delta v={n.mom} /></span>
                <span style={{ color: SRC[n.origin] }}>asal {SRC_LABEL[n.origin]}</span>
                <span className="dim">pickup media {n.pickup}</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel kicker={"Narasi " + sel.id} title={sel.text}>
        <div className="kv">
          <div><span>Volume</span><b>{sel.vol}% dari percakapan</b></div>
          <div><span>Momentum 7 hari</span><b>{sel.mom > 0 ? "+" : ""}{sel.mom} poin</b></div>
          <div><span>Sentiment</span><b>{sel.sent > 0 ? "+" : ""}{sel.sent}</b></div>
          <div><span>Titik asal</span><b>{SRC_LABEL[sel.origin]}</b></div>
          <div><span>Pickup media</span><b>{sel.pickup} artikel</b></div>
          <div><span>Segmen dominan</span><b>Concerned, Volatile</b></div>
          <div><span>Sebaran</span><b>Urban Jawa, kota besar Sumatera</b></div>
        </div>
        <div className="quote">
          Contoh representatif dari 12.431 respons terbuka, sudah dianonimkan dan dipilih dari
          klaster tema terbesar. Identitas responden tidak disimpan bersama teks.
        </div>
        <Provenance
          method="Embedding + clustering HDBSCAN, pelabelan narasi oleh LLM dengan verifikasi manusia"
          n="214.600 mention"
          confidence="Sedang"
          limits="Batas antar-narasi tidak selalu tegas; 6,2% mention tidak terklaster"
        />
      </Panel>
    </div>
  );
}

function SegmentView() {
  return (
    <>
      <Panel kicker="Enam kelompok, bukan positif/negatif" title="Public Segments">
        <div className="segbar">
          {segments.map((s) => (
            <div
              key={s.name}
              className="segbar-seg"
              style={{
                width: s.size + "%",
                background: s.sent > 30 ? "var(--pos)" : s.sent > 0 ? "#5FA98A" : s.sent > -40 ? "var(--warn)" : "var(--neg)",
              }}
              title={s.name + " " + s.size + "%"}
            >
              <span>{s.size}%</span>
            </div>
          ))}
        </div>
        <table className="tbl">
          <thead>
            <tr><th>Segmen</th><th>Ukuran</th><th>Sentiment</th><th>Trust</th><th>Usia inti</th><th>Wilayah</th><th>Isu utama</th><th>Volatilitas</th></tr>
          </thead>
          <tbody>
            {segments.map((s) => (
              <tr key={s.name}>
                <td className="strong">{s.name}</td>
                <td>{s.size}%</td>
                <td className={s.sent < 0 ? "neg" : "pos"}>{s.sent > 0 ? "+" : ""}{s.sent}</td>
                <td>{s.trust}</td>
                <td>{s.age}</td>
                <td className="dim">{s.geo}</td>
                <td className="dim">{s.concern}</td>
                <td>{s.vol}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note">
          <Info size={13} /> Segmentasi dibentuk dari respons survei dan variabel demografis yang
          dikumpulkan dengan consent. Platform tidak melakukan inferensi terhadap atribut sensitif
          seperti agama, etnisitas, atau afiliasi politik individu.
        </p>
        <Provenance
          method="Latent class analysis, 6 kelas, BIC minimum"
          n="8.940"
          confidence="Tinggi"
          limits="Entropi 0,82 — sebagian responden punya probabilitas keanggotaan ganda"
        />
      </Panel>
    </>
  );
}

function GeoView() {
  const [sel, setSel] = useState(provinces[3]);
  const color = (v) => (v >= 75 ? "#2FBF71" : v >= 70 ? "#7FB45C" : v >= 66 ? "#F5B301" : v >= 63 ? "#EF8A3C" : "#EF4B4B");
  return (
    <div className="grid-2">
      <Panel kicker="Diurutkan menurut indeks" title="Opini per provinsi">
        <div className="geo">
          {[...provinces].sort((a, b) => b.poi - a.poi).map((p) => (
            <button
              key={p.p}
              className={"geo-t" + (sel.p === p.p ? " geo-on" : "")}
              onClick={() => setSel(p)}
              style={{ borderLeftColor: color(p.poi) }}
            >
              <span className="geo-n">{p.p}</span>
              <span className="geo-v" style={{ color: color(p.poi) }}>{p.poi}</span>
            </button>
          ))}
        </div>
        <div className="legend">
          <span>Rendah</span>
          {["#EF4B4B", "#EF8A3C", "#F5B301", "#7FB45C", "#2FBF71"].map((c) => (
            <i key={c} style={{ background: c }} />
          ))}
          <span>Tinggi</span>
        </div>
      </Panel>

      <Panel kicker="Detail wilayah" title={sel.p}>
        <div className="kv">
          <div><span>Public Opinion Index</span><b>{sel.poi}</b></div>
          <div><span>Trust</span><b>{sel.trust}</b></div>
          <div><span>Approval</span><b>{sel.approval}%</b></div>
          <div><span>Isu teratas</span><b>{sel.top}</b></div>
          <div><span>Perubahan periode</span><b><Delta v={sel.d} /></b></div>
          <div><span>Sampel tercapai</span><b>{sel.n}</b></div>
          <div><span>Margin of error</span><b>±{(98 / Math.sqrt(sel.n)).toFixed(1)} pp</b></div>
        </div>
        <p className="note">
          <Info size={13} /> Estimasi provinsi hanya ditampilkan bila sampel tercapai memenuhi ambang
          minimum. Provinsi dengan n di bawah 250 tidak diberi skor dan ditandai sebagai data tidak cukup.
        </p>
        <Provenance
          method="Estimasi area kecil dengan pembobotan pasca-stratifikasi"
          n={String(sel.n)}
          ci={"±" + (98 / Math.sqrt(sel.n)).toFixed(1) + " pp"}
          confidence={sel.n > 400 ? "Tinggi" : "Sedang"}
          limits="Tidak dapat diturunkan ke tingkat kabupaten/kota tanpa sampel tambahan"
        />
      </Panel>
    </div>
  );
}

function ForecastView() {
  const [price, setPrice] = useState(0);
  const [comms, setComms] = useState(0);
  const [media, setMedia] = useState(0);

  const sim = useMemo(() => {
    const impact = -0.72 * price + 0.34 * comms - 0.28 * media;
    return forecastBase.map((f, i) => {
      const w = i / (forecastBase.length - 1);
      const shift = impact * w;
      const spread = (f.high - f.low) / 2 + Math.abs(impact) * w * 0.6;
      const exp = f.exp + shift;
      return { d: f.d, exp: +exp.toFixed(1), low: +(exp - spread).toFixed(1), high: +(exp + spread).toFixed(1) };
    });
  }, [price, comms, media]);

  const end = sim[sim.length - 1];
  const active = price !== 0 || comms !== 0 || media !== 0;

  return (
    <>
      <Panel
        kicker="Proyeksi model, bukan kepastian"
        title="Opinion Forecast"
        right={active && <span className="pill pill-sim">SIMULASI AKTIF</span>}
      >
        <div className="chart">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={sim} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid stroke="#1A2532" vertical={false} />
              <XAxis dataKey="d" {...chartAxis} tickLine={false} axisLine={{ stroke: "#1F2B3C" }} />
              <YAxis domain={[55, 82]} {...chartAxis} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tipStyle} />
              <Area type="monotone" dataKey="high" stroke="none" fill="#4DA3FF" fillOpacity={0.14} name="Batas atas" />
              <Area type="monotone" dataKey="low" stroke="none" fill="#0A1017" fillOpacity={1} name="Batas bawah" />
              <Line type="monotone" dataKey="exp" stroke="#4DA3FF" strokeWidth={2.5} dot={false} name="Ekspektasi" />
              <ReferenceLine y={72.4} stroke="#41526B" strokeDasharray="3 3" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="fc-out">
          <div><span className="kicker">Sekarang</span><b>72.4</b></div>
          <div><span className="kicker">Ekspektasi H+30</span><b>{end.exp}</b></div>
          <div><span className="kicker">Rentang H+30</span><b>{end.low} – {end.high}</b></div>
          <div><span className="kicker">Perubahan</span><b><Delta v={+(end.exp - 72.4).toFixed(1)} /></b></div>
        </div>
      </Panel>

      <Panel kicker="What-if" title="Uji skenario">
        <div className="sliders">
          {[
            { l: "Kenaikan harga pangan", v: price, s: setPrice, min: 0, max: 10, u: "%", h: "Setiap 1% kenaikan diasosiasikan dengan −0,72 poin indeks pada horizon 30 hari" },
            { l: "Intensitas komunikasi publik", v: comms, s: setComms, min: 0, max: 10, u: " unit", h: "Efek positif, melandai setelah titik jenuh" },
            { l: "Eskalasi liputan negatif", v: media, s: setMedia, min: 0, max: 10, u: " unit", h: "Memperlebar ketidakpastian, bukan hanya menurunkan rata-rata" },
          ].map((s) => (
            <div key={s.l} className="slider">
              <div className="slider-top">
                <label htmlFor={s.l}>{s.l}</label>
                <span className="slider-v">{s.v}{s.u}</span>
              </div>
              <input id={s.l} type="range" min={s.min} max={s.max} value={s.v} onChange={(e) => s.s(Number(e.target.value))} />
              <div className="slider-h">{s.h}</div>
            </div>
          ))}
        </div>
        <div className="sim-out">
          <div className="sim-t">Hasil simulasi</div>
          <p>
            Skenario ini memproyeksikan indeks berada di sekitar <b>{end.exp}</b> pada H+30,
            dengan rentang <b>{end.low}–{end.high}</b>. Segmen yang paling responsif adalah
            <b> Concerned</b> dan <b>Volatile</b>; wilayah paling terdampak adalah DKI Jakarta,
            Banten, dan Jawa Barat.
          </p>
          <p className="sim-warn">
            Angka di atas adalah keluaran simulasi berdasarkan koefisien historis, bukan prediksi
            yang dijamin dan bukan dasar tunggal untuk pengambilan keputusan.
          </p>
        </div>
        <Provenance
          method="Model state-space dengan regresor eksogen"
          n="36 bulan data historis"
          ci="Interval prediksi 80%"
          confidence="Sedang"
          limits="Koefisien diestimasi pada periode tanpa guncangan besar; tidak valid untuk skenario ekstrem"
        />
      </Panel>
    </>
  );
}

function BriefView() {
  const items = [
    ["Apa yang terjadi", "Public Opinion Index turun 4,2 poin dalam empat minggu, ke 72,4. Approval bertahan di 74%, tetapi Trust sudah turun 2,1 poin lebih dulu."],
    ["Mengapa", "Penurunan terkonsentrasi pada isu biaya hidup. Harga pangan naik 6,2 poin sebagai perhatian utama, biaya transportasi naik 9,4 poin dan menjadi isu dengan pertumbuhan tercepat."],
    ["Siapa", "Segmen Concerned (19% publik) dan Volatile (8%) menunjukkan pergeseran terbesar. Keduanya didominasi usia 25–34 di wilayah urban."],
    ["Di mana", "Tiga wilayah dengan penurunan tertinggi: DKI Jakarta (−6,1), Banten (−5,3), NTB (−4,8). Jawa Tengah dan Yogyakarta relatif stabil."],
    ["Apa berikutnya", "Model memperkirakan stabilisasi dalam 7 hari di kisaran 69,0–73,6, dengan ekspektasi 71,2. Ketidakpastian melebar bila liputan negatif berlanjut."],
    ["Apa yang perlu diawasi", "Harga pangan, Trust Index, dan kecepatan pertumbuhan Narasi B. Ketiganya memiliki hubungan paling kuat dengan pergerakan indeks pada periode ini."],
  ];
  return (
    <Panel tone="light">
      <div className="brief">
        <div className="brief-head">
          <div>
            <div className="kicker">Executive brief · Minggu 29 · Dibuat otomatis, ditinjau manusia</div>
            <h1 className="brief-h1">Opini publik melemah pada isu biaya hidup</h1>
          </div>
          <div className="brief-badge">Ditinjau oleh Research Director · 19 Agu</div>
        </div>
        <dl className="brief-list">
          {items.map(([q, a]) => (
            <div key={q}>
              <dt>{q}</dt>
              <dd>{a}</dd>
            </div>
          ))}
        </dl>
        <div className="brief-foot">
          Setiap kalimat pada ringkasan ini tertaut ke data agregat yang mendasarinya. Rekomendasi
          tindakan disusun sebagai opsi; keputusan tetap berada pada pengambil kebijakan.
        </div>
      </div>
    </Panel>
  );
}

function GovernanceView() {
  return (
    <>
      <Panel kicker="Wajib pada setiap keluaran AI" title="Jejak keputusan model">
        <table className="tbl">
          <thead><tr><th>Keluaran</th><th>Model</th><th>Metode</th><th>Confidence</th><th>Tinjauan</th></tr></thead>
          <tbody>
            {[
              ["Ringkasan eksekutif W29", "claude-sonnet-4-6", "RAG atas data agregat", "Sedang", "Disetujui"],
              ["Pelabelan narasi A–D", "embedding + LLM", "Clustering + verifikasi manual", "Sedang", "Disetujui"],
              ["Forecast 30 hari", "state-space", "Estimasi historis", "Sedang", "Menunggu"],
              ["Segmentasi publik", "latent class", "Statistik, bukan LLM", "Tinggi", "Disetujui"],
              ["Deteksi respons kualitas rendah", "rule + anomaly", "Ambang statistik", "Tinggi", "Perlu tinjauan"],
            ].map((r) => (
              <tr key={r[0]}>
                <td className="strong">{r[0]}</td><td className="mono">{r[1]}</td><td className="dim">{r[2]}</td>
                <td>{r[3]}</td>
                <td><span className={"pill " + (r[4] === "Disetujui" ? "pill-ok" : "pill-warn")}>{r[4]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid-2">
        <Panel kicker="Privasi" title="Yang tidak dilakukan platform ini">
          <ul className="nolist">
            <li>Tidak menyimpan identitas responden bersama jawabannya.</li>
            <li>Tidak menyimpulkan agama, etnisitas, orientasi, atau afiliasi politik individu.</li>
            <li>Tidak menyatakan akun tertentu mengendalikan opini publik — hanya estimasi pengaruh disertai metode.</li>
            <li>Tidak mengambil keputusan otomatis yang berdampak pada individu.</li>
            <li>Tidak memperlakukan sentiment media sosial sebagai representasi populasi.</li>
          </ul>
        </Panel>
        <Panel kicker="Kualitas data" title="Data Quality Score">
          <div className="dq">
            {[["Kelengkapan", 96], ["Duplikat", 99], ["Kualitas respons", 87], ["Konsistensi", 92], ["Keseimbangan sampel", 81], ["Metadata", 94]].map(([l, v]) => (
              <div key={l} className="dq-row">
                <span>{l}</span>
                <Bar100 value={v} color={v >= 90 ? "var(--pos)" : v >= 80 ? "var(--warn)" : "var(--neg)"} />
                <b>{v}</b>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  SHELL                                                              */
/* ------------------------------------------------------------------ */

export default function App() {
  const [view, setView] = useState("command");
  const [navOpen, setNavOpen] = useState(false);
  const current = NAV.find((n) => n.id === view);

  const views = {
    command: <CommandCenter />, index: <IndexView />, consistency: <Consistency />,
    narrative: <NarrativeView />, segments: <SegmentView />, geo: <GeoView />,
    forecast: <ForecastView />, brief: <BriefView />, governance: <GovernanceView />,
  };

  return (
    <div className="app">
      <style>{CSS}</style>

      <aside className={"nav" + (navOpen ? " nav-open" : "")}>
        <div className="brand">
          <Activity size={18} />
          <div>
            <div className="brand-n">PUBLIC OPINION</div>
            <div className="brand-s">Intelligence Platform</div>
          </div>
        </div>
        <nav>
          {NAV.map((n) => {
            const I = n.icon;
            return (
              <button
                key={n.id}
                className={"nav-i" + (view === n.id ? " nav-on" : "")}
                onClick={() => { setView(n.id); setNavOpen(false); }}
              >
                <I size={15} />
                <span>{n.label}</span>
                {view === n.id && <ChevronRight size={13} className="nav-c" />}
              </button>
            );
          })}
        </nav>
        <div className="nav-foot">
          <div className="kicker">Proyek aktif</div>
          <div className="proj">Persepsi Kebijakan Nasional 2026</div>
          <div className="proj-s">Gelombang 12 · Demo data sintetis</div>
        </div>
      </aside>

      <main className="main">
        <header className="top">
          <button className="burger" onClick={() => setNavOpen((v) => !v)} aria-label="Buka menu">☰</button>
          <div>
            <div className="kicker">{current.label}</div>
            <div className="top-t">Persepsi Kebijakan Nasional 2026</div>
          </div>
          <div className="top-r">
            <span className="dot" /> Data diperbarui 4 menit lalu
          </div>
        </header>
        <div className="body">{views[view]}</div>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

.app *, .app *::before, .app *::after { box-sizing: border-box; }
.app {
  --ink:#0A1017; --panel:#0F1720; --panel2:#131D28; --line:#1F2B3C;
  --txt:#E6EDF6; --txt2:#8FA0B5; --txt3:#5C6E85;
  --survey:#4DA3FF; --social:#FF7A45; --media:#9B8AFB;
  --pos:#2FBF71; --warn:#F5B301; --neg:#EF4B4B;
  display:flex; min-height:100vh; background:var(--ink); color:var(--txt);
  font-family:'IBM Plex Sans', system-ui, sans-serif; font-size:14px; line-height:1.5;
}
.app h1,.app h2 { font-family:'Archivo', system-ui, sans-serif; margin:0; }
.kicker {
  font-family:'IBM Plex Mono', monospace; font-size:9.5px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--txt3); font-weight:500;
}
.mono { font-family:'IBM Plex Mono', monospace; font-size:12px; }
.dim { color:var(--txt2); }
.strong { color:var(--txt); font-weight:600; }
.pos { color:var(--pos); } .neg { color:var(--neg); }
.app button:focus-visible, .app input:focus-visible { outline:2px solid var(--survey); outline-offset:2px; }

/* nav */
.nav {
  width:222px; flex:0 0 222px; background:#080D13; border-right:1px solid var(--line);
  display:flex; flex-direction:column; position:sticky; top:0; height:100vh;
}
.brand { display:flex; gap:9px; align-items:center; padding:16px 14px; border-bottom:1px solid var(--line); color:var(--survey); }
.brand-n { font-family:'Archivo',sans-serif; font-size:12px; font-weight:700; letter-spacing:.06em; color:var(--txt); }
.brand-s { font-family:'IBM Plex Mono',monospace; font-size:9.5px; color:var(--txt3); letter-spacing:.08em; text-transform:uppercase; }
.nav nav { padding:8px 6px; display:flex; flex-direction:column; gap:1px; overflow-y:auto; }
.nav-i {
  display:flex; align-items:center; gap:9px; width:100%; padding:8px 9px; border:0; border-radius:3px;
  background:transparent; color:var(--txt2); font:inherit; font-size:12.5px; cursor:pointer; text-align:left;
}
.nav-i:hover { background:#0F1720; color:var(--txt); }
.nav-on { background:#11202F; color:var(--txt); box-shadow:inset 2px 0 0 var(--survey); }
.nav-c { margin-left:auto; color:var(--survey); }
.nav-foot { margin-top:auto; padding:14px; border-top:1px solid var(--line); }
.proj { font-size:12.5px; font-weight:600; margin-top:4px; }
.proj-s { font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--txt3); margin-top:2px; }

/* main */
.main { flex:1; min-width:0; }
.top {
  display:flex; align-items:center; gap:12px; padding:12px 20px;
  border-bottom:1px solid var(--line); background:#080D13; position:sticky; top:0; z-index:5;
}
.top-t { font-family:'Archivo',sans-serif; font-size:15px; font-weight:600; letter-spacing:-.01em; }
.top-r { margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--txt3); display:flex; align-items:center; gap:6px; }
.dot { width:6px; height:6px; border-radius:50%; background:var(--pos); box-shadow:0 0 0 3px rgba(47,191,113,.15); }
.burger { display:none; background:transparent; border:1px solid var(--line); color:var(--txt2); border-radius:3px; padding:4px 8px; cursor:pointer; }
.body { padding:20px; display:flex; flex-direction:column; gap:16px; max-width:1400px; }

/* panels */
.panel { background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:16px; }
.panel-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:14px; }
.panel-title { font-size:16px; font-weight:600; letter-spacing:-.01em; margin-top:3px; }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.chart { margin:0 -4px; }
.note { display:flex; gap:7px; align-items:flex-start; font-size:12px; color:var(--txt2); margin:12px 0 0; }
.note svg { flex:0 0 auto; margin-top:2px; color:var(--txt3); }

/* provenance */
.prov {
  display:flex; flex-wrap:wrap; gap:4px 16px; margin-top:14px; padding-top:10px; border-top:1px dashed #1B2534;
  font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.03em; color:var(--txt3);
}
.prov b { color:#43566E; font-weight:500; letter-spacing:.1em; margin-right:5px; }
.prov-lim { color:#6B7F96; }

/* stats */
.stat-row { display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr; gap:16px; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:14px 16px; }
.stat-v { font-family:'Archivo',sans-serif; font-size:34px; font-weight:600; letter-spacing:-.03em; margin-top:6px; font-variant-numeric:tabular-nums; }
.stat-big .stat-v { font-size:48px; color:var(--survey); }
.stat-u { font-size:14px; color:var(--txt3); margin-left:4px; letter-spacing:0; }
.stat-foot { display:flex; align-items:center; gap:8px; margin-top:6px; }
.delta { display:inline-flex; align-items:center; gap:2px; font-family:'IBM Plex Mono',monospace; font-size:11px; }
.delta.up { color:var(--pos); } .delta.down { color:var(--neg); } .delta.flat { color:var(--txt3); }
.pill { font-family:'IBM Plex Mono',monospace; font-size:9px; letter-spacing:.1em; text-transform:uppercase; padding:2px 6px; border-radius:2px; }
.pill-warn { background:rgba(245,179,1,.14); color:var(--warn); }
.pill-ok { background:rgba(47,191,113,.13); color:var(--pos); }
.pill-sim { background:rgba(155,138,251,.15); color:var(--media); }

/* divergence band — signature */
.dvg { background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:18px 20px 16px; }
.dvg-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
.dvg-gap { text-align:right; }
.dvg-gap-n { font-family:'Archivo',sans-serif; font-size:38px; font-weight:700; letter-spacing:-.04em; color:var(--social); line-height:1; }
.dvg-track { position:relative; height:132px; margin:22px 0 6px; }
.dvg-track::after { content:''; position:absolute; left:0; right:0; bottom:22px; height:1px; background:#243244; }
.dvg-span { position:absolute; bottom:22px; height:8px; background:repeating-linear-gradient(90deg,#1E2C3D 0 4px,transparent 4px 8px); border-left:1px solid #34465C; border-right:1px solid #34465C; }
.dvg-mark { position:absolute; bottom:22px; }
.dvg-stem { position:absolute; bottom:0; width:1px; opacity:.5; }
.dvg-dot { position:absolute; bottom:-4px; left:-4px; width:9px; height:9px; border-radius:50%; }
.dvg-tag {
  position:absolute; transform:translateX(-50%); white-space:nowrap; padding:2px 7px;
  background:#0A1017; border:1px solid; border-radius:2px;
  font-family:'IBM Plex Mono',monospace; font-size:10.5px; letter-spacing:.05em;
}
.dvg-scale { position:absolute; left:0; right:0; bottom:0; display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace; font-size:9.5px; color:var(--txt3); }
.dvg-read { font-size:13px; color:var(--txt2); margin:14px 0 0; max-width:76ch; }
.dvg-read b { color:var(--txt); }

/* issues */
.issues { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:13px; }
.issue-top { display:flex; justify-content:space-between; font-size:13px; margin-bottom:5px; }
.issue-name { font-weight:500; }
.issue-share { font-family:'IBM Plex Mono',monospace; color:var(--txt2); }
.issue-meta { display:flex; gap:12px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--txt3); margin-top:5px; }
.bar100 { height:5px; background:#16202C; border-radius:1px; overflow:hidden; }
.bar100 > div { height:100%; }

/* timeline */
.tl { list-style:none; margin:0; padding:0; border-left:1px solid var(--line); }
.tl li { position:relative; padding:7px 0 7px 16px; display:flex; gap:10px; align-items:baseline; font-size:13px; }
.tl li::before { content:''; position:absolute; left:-3.5px; top:14px; width:6px; height:6px; border-radius:50%; background:var(--txt3); }
.tl-event::before { background:var(--survey) !important; }
.tl-media::before { background:var(--media) !important; }
.tl-alert::before { background:var(--neg) !important; }
.tl-d { font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--txt3); flex:0 0 46px; }
.tl-e { flex:1; }
.tl-v { font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--txt2); }

/* alerts */
.alerts { display:flex; flex-direction:column; gap:9px; }
.alert { display:flex; gap:10px; padding:11px 12px; border-radius:3px; background:var(--panel2); border-left:2px solid var(--txt3); }
.alert svg { flex:0 0 auto; margin-top:1px; color:var(--txt3); }
.alert-high { border-left-color:var(--neg); } .alert-high svg { color:var(--neg); }
.alert-med { border-left-color:var(--warn); } .alert-med svg { color:var(--warn); }
.alert-t { font-size:13px; font-weight:500; }
.alert-d { font-size:12px; color:var(--txt2); margin-top:3px; }

/* POI */
.poi-wrap { display:grid; grid-template-columns:220px 1fr; gap:26px; }
.poi-n { font-family:'Archivo',sans-serif; font-size:66px; font-weight:700; letter-spacing:-.045em; line-height:1; color:var(--survey); font-variant-numeric:tabular-nums; }
.poi-scale { font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--txt3); margin-top:2px; }
.poi-meta { margin-top:16px; display:flex; flex-direction:column; gap:6px; font-size:12px; color:var(--txt2); }
.poi-meta b { display:block; font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--txt3); font-weight:500; }
.poi-dims { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px 18px; }
.dim-head { display:flex; align-items:center; gap:7px; margin-bottom:6px; }
.dim-src { width:7px; height:7px; border-radius:1px; flex:0 0 auto; }
.dim-label { font-size:12.5px; font-weight:500; }
.dim-score { margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--txt2); }
.dim-w { display:flex; align-items:center; gap:8px; margin-top:7px; }
.dim-w input { flex:1; }
.dim-wv { font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--txt2); width:28px; text-align:right; }
.dim-note { font-size:11px; color:var(--txt3); margin-top:4px; }
.app input[type=range] { -webkit-appearance:none; appearance:none; height:3px; background:#22303F; border-radius:2px; }
.app input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:11px; height:11px; border-radius:50%; background:var(--survey); cursor:pointer; }
.app input[type=range]::-moz-range-thumb { width:11px; height:11px; border:0; border-radius:50%; background:var(--survey); cursor:pointer; }

/* consistency */
.cons { display:flex; flex-direction:column; gap:12px; margin-bottom:18px; }
.cons-row { display:grid; grid-template-columns:64px 1fr 96px 130px; gap:14px; align-items:center; }
.cons-label { font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.12em; }
.cons-v { font-family:'Archivo',sans-serif; font-size:22px; font-weight:600; letter-spacing:-.02em; }
.pct { font-family:'IBM Plex Sans',sans-serif; font-size:10.5px; color:var(--txt3); margin-left:4px; font-weight:400; }
.cons-n { font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:var(--txt3); text-align:right; }
.reads { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.read { background:var(--panel2); border-radius:3px; padding:12px 13px; }
.read-t { font-size:13px; font-weight:600; margin-bottom:5px; }
.read-d { font-size:12.5px; color:var(--txt2); }

/* tables */
.tbl { width:100%; border-collapse:collapse; font-size:12.5px; }
.tbl th {
  text-align:left; font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--txt3); font-weight:500; padding:0 10px 7px 0; border-bottom:1px solid var(--line);
}
.tbl td { padding:8px 10px 8px 0; border-bottom:1px solid #16202C; }

/* narrative */
.narrs { display:flex; flex-direction:column; gap:8px; }
.narr { width:100%; text-align:left; background:var(--panel2); border:1px solid transparent; border-radius:3px; padding:11px 12px; cursor:pointer; color:inherit; font:inherit; }
.narr:hover { border-color:#28374A; }
.narr-on { border-color:var(--survey); background:#111E2C; }
.narr-head { display:flex; align-items:baseline; gap:9px; margin-bottom:7px; }
.narr-id { font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--txt3); }
.narr-t { flex:1; font-size:13px; font-weight:500; }
.narr-v { font-family:'IBM Plex Mono',monospace; font-size:13px; }
.narr-meta { display:flex; flex-wrap:wrap; gap:12px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--txt3); margin-top:6px; }
.kv { display:flex; flex-direction:column; gap:0; }
.kv > div { display:flex; justify-content:space-between; gap:16px; padding:8px 0; border-bottom:1px solid #16202C; font-size:12.5px; }
.kv span { color:var(--txt3); }
.quote { margin-top:14px; padding:11px 13px; background:var(--panel2); border-left:2px solid var(--media); font-size:12.5px; color:var(--txt2); border-radius:0 3px 3px 0; }

/* segments */
.segbar { display:flex; height:34px; border-radius:3px; overflow:hidden; margin-bottom:18px; gap:1px; }
.segbar-seg { display:flex; align-items:center; justify-content:center; font-family:'IBM Plex Mono',monospace; font-size:10.5px; color:#0A1017; font-weight:500; }
.nolist { margin:0; padding-left:16px; display:flex; flex-direction:column; gap:8px; font-size:12.5px; color:var(--txt2); }
.dq { display:flex; flex-direction:column; gap:11px; }
.dq-row { display:grid; grid-template-columns:150px 1fr 32px; gap:12px; align-items:center; font-size:12.5px; }
.dq-row b { font-family:'IBM Plex Mono',monospace; text-align:right; }

/* geo */
.geo { display:grid; grid-template-columns:1fr 1fr; gap:5px; }
.geo-t { display:flex; justify-content:space-between; align-items:center; gap:8px; padding:8px 10px; background:var(--panel2); border:1px solid transparent; border-left:3px solid; border-radius:2px; cursor:pointer; color:inherit; font:inherit; text-align:left; }
.geo-t:hover { background:#17222F; }
.geo-on { border-color:var(--survey); border-left-width:3px; }
.geo-n { font-size:12.5px; }
.geo-v { font-family:'Archivo',sans-serif; font-size:15px; font-weight:600; }
.legend { display:flex; align-items:center; gap:4px; margin-top:14px; font-family:'IBM Plex Mono',monospace; font-size:9.5px; color:var(--txt3); }
.legend i { width:22px; height:7px; border-radius:1px; }

/* forecast */
.fc-out { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }
.fc-out b { display:block; font-family:'Archivo',sans-serif; font-size:20px; font-weight:600; margin-top:4px; }
.sliders { display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; }
.slider-top { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:7px; }
.slider-top label { font-size:12.5px; font-weight:500; }
.slider-v { font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--survey); }
.slider input { width:100%; }
.slider-h { font-size:11px; color:var(--txt3); margin-top:6px; }
.sim-out { margin-top:18px; padding:14px 15px; background:var(--panel2); border-radius:3px; border-left:2px solid var(--media); }
.sim-t { font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.12em; text-transform:uppercase; color:var(--media); margin-bottom:7px; }
.sim-out p { margin:0 0 8px; font-size:13px; color:var(--txt2); }
.sim-out b { color:var(--txt); }
.sim-warn { font-size:11.5px !important; color:var(--txt3) !important; margin:0 !important; }

/* brief — inverted, meant to be read and printed */
.panel-light { background:#F2EFE9; border-color:#DDD7CC; color:#1A1D21; padding:34px 38px; }
.brief-head { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; padding-bottom:20px; border-bottom:2px solid #1A1D21; }
.panel-light .kicker { color:#7A736A; }
.brief-h1 { font-family:'Archivo',sans-serif; font-size:26px; font-weight:700; letter-spacing:-.025em; margin-top:6px; max-width:24ch; }
.brief-badge { font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.08em; color:#7A736A; text-align:right; }
.brief-list { margin:0; }
.brief-list > div { display:grid; grid-template-columns:190px 1fr; gap:24px; padding:18px 0; border-bottom:1px solid #DDD7CC; }
.brief-list dt { font-family:'Archivo',sans-serif; font-size:15px; font-weight:600; letter-spacing:-.01em; }
.brief-list dd { margin:0; font-size:14px; line-height:1.6; color:#33383E; max-width:70ch; }
.brief-foot { margin-top:20px; font-family:'IBM Plex Mono',monospace; font-size:10px; line-height:1.7; color:#7A736A; max-width:80ch; }

/* responsive */
@media (max-width:1080px) {
  .stat-row { grid-template-columns:1fr 1fr; }
  .poi-wrap { grid-template-columns:1fr; }
  .poi-dims { grid-template-columns:1fr 1fr; }
  .sliders { grid-template-columns:1fr; }
  .reads { grid-template-columns:1fr; }
}
@media (max-width:860px) {
  .nav { position:fixed; z-index:20; transform:translateX(-100%); transition:transform .2s; }
  .nav-open { transform:translateX(0); }
  .burger { display:block; }
  .grid-2 { grid-template-columns:1fr; }
  .geo { grid-template-columns:1fr; }
  .fc-out { grid-template-columns:1fr 1fr; }
  .cons-row { grid-template-columns:56px 1fr 80px; }
  .cons-n { display:none; }
  .brief-list > div { grid-template-columns:1fr; gap:6px; }
  .panel-light { padding:22px; }
  .body { padding:14px; }
  .tbl { font-size:11.5px; }
}
@media (max-width:560px) {
  .stat-row { grid-template-columns:1fr; }
  .poi-dims { grid-template-columns:1fr; }
  .dvg-track { height:150px; }
}
@media (prefers-reduced-motion:reduce) { .app * { transition:none !important; animation:none !important; } }
`;
