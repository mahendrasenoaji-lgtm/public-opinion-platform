import { Info } from "lucide-react";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { apiOrNull } from "@/lib/api";
import { getCurrentProject } from "@/lib/currentProject";
import { ImpactForm } from "./ImpactForm";

export const dynamic = "force-dynamic";

interface SegmentOut {
  name: string;
}

export default async function DampakPage() {
  const { id: projectId, name, is_demo: isDemo } = await getCurrentProject();
  const segments = (await apiOrNull<SegmentOut[]>(`/projects/${projectId}/segments`)) ?? [];

  return (
    <>
      <PageHeader kicker="Communication Impact" title={name} isDemo={isDemo} />
      <div className="body">
        <Panel kicker="Desain pembanding" title="Ukur dampak komunikasi">
          {/* Ini satu-satunya modul di platform ini yang boleh mengeluarkan
              klaim efek. AIEnvelope menolak bahasa kausal kecuali method-nya
              menyebut desain pembanding — dan modul ini yang mengisinya. */}
          <p style={{ fontSize: 13, color: "var(--txt2)", margin: "0 0 18px", maxWidth: 720 }}>
            Halaman ini memakai <b>difference-in-differences</b>: membandingkan
            perubahan pada kelompok yang terpapar komunikasi dengan perubahan pada
            kelompok yang tidak, di periode yang sama. Tanpa kelompok pembanding,
            yang bisa dihitung hanyalah selisih sebelum-sesudah — dan selisih itu
            tidak bisa dipisahkan dari tren yang memang sudah berjalan. Karena itu
            modul ini menolak bekerja tanpa pembanding, dan tidak ada cara untuk
            melewatinya.
          </p>

          <ImpactForm projectId={projectId} segments={segments.map((s) => s.name)} />
        </Panel>

        <Panel kicker="Syarat" title="Apa yang dibutuhkan sebuah klaim efek">
          <ol className="nolist">
            <li>
              <b>Empat sel terukur.</b> Kelompok terpapar dan kelompok pembanding,
              masing-masing pada periode sebelum dan sesudah. Snapshot yang tidak
              lengkap ditolak, bukan diperkirakan.
            </li>
            <li>
              <b>Tren paralel sebelum perlakuan.</b> Inti desain ini adalah asumsi
              bahwa tanpa perlakuan, kedua kelompok akan bergerak sejajar. Kalau
              sebelum perlakuan saja keduanya sudah bergerak berbeda, asumsi itu
              jatuh dan angkanya tidak berarti apa-apa.
            </li>
            <li>
              <b>Ketidakpastian yang bisa dihitung.</b> Snapshot tanpa interval
              kepercayaan ditolak. Efek tanpa ketidakpastian adalah angka yang
              menyembunyikan apa yang tidak diketahui.
            </li>
          </ol>

          <p className="note">
            <Info size={13} />
            Yang tetap tidak bisa dijawab: siapa yang berubah, apakah efeknya
            bertahan, dan apakah ada peristiwa lain yang mengenai kelompok terpapar
            pada waktu yang sama. Data ini tidak bisa membuktikan tidak ada.
          </p>
        </Panel>
      </div>
    </>
  );
}
