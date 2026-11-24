"""Tes unit services/profiling.py (P11): estimasi gender, umur, minat."""

from __future__ import annotations

from app.services import profiling as p


class TestPernyataanDiri:
    def test_ibu_dikenali_sebagai_perempuan(self) -> None:
        (st,) = p.self_statements("Saya ini ibu dua anak, harga beras makin mahal")
        assert st.gender == "P"
        assert st.age is None

    def test_reduplikasi_dan_huruf_berulang(self) -> None:
        assert p.self_statements("kami emak2 pusing")[0].gender == "P"
        assert p.self_statements("kami ibu-ibu pusing")[0].gender == "P"
        assert p.self_statements("gue cowooook biasa")[0].gender == "L"

    def test_negasi_dilewati(self) -> None:
        assert p.self_statements("saya bukan ibu ibu yang suka gosip") == []
        assert p.self_statements("aku gak mahasiswa lagi") == []

    def test_sapaan_ke_orang_lain_tidak_dipakai(self) -> None:
        assert p.self_statements("Bu, tolong dengar rakyat. Mas, mbak, bro") == []
        assert p.self_statements("ibu menteri harus mundur") == []

    def test_umur_dari_peran_dan_angka(self) -> None:
        assert p.self_statements("gw masih anak SMA")[0].age == "<=17"
        assert p.self_statements("gw anak SMA")[0].age == "<=17"
        assert p.self_statements("aku mahasiswi semester 3")[0].gender == "P"
        assert p.self_statements("aku mahasiswi semester 3")[0].age == "18-24"
        assert p.self_statements("umur saya 52 tahun")[0].age == "45+"
        assert p.self_statements("saya 23 thn")[0].age == "18-24"
        assert p.self_statements("saya sudah pensiun")[0].age == "45+"

    def test_umur_tanpa_kata_ganti_bukan_umur_penulis(self) -> None:
        assert p.self_statements("umur gibran 39 tahun sudah wapres") == []
        assert p.self_statements("di umur 39 sudah jadi wapres") == []
        assert p.self_statements("umurku 19")[0].age == "18-24"

    def test_lama_waktu_bukan_umur(self) -> None:
        assert p.self_statements("saya 20 tahun kerja di jakarta") == []
        assert p.self_statements("saya sudah 30 tahun jadi guru") == []
        assert p.self_statements("saya 12 tahun loyalis gerindra") == []
        assert p.self_statements("saya sudah 40 tahun mengantri bbm") == []
        assert p.self_statements("saya 30 tahun, belum menikah")[0].age == "25-34"

    def test_kita_bukan_penulis(self) -> None:
        assert p.self_statements("kita bapak bapak harus kompak") == []
        assert p.self_statements("kami ibu ibu kecewa")[0].gender == "P"

    def test_sapaan_dan_opini_bukan_identitas(self) -> None:
        for text in [
            "menurut saya bpk prabowo tidak perlu wakil",
            "salam hormat saya bapak gibran dari aceh",
            "buat sy bapak jokowi tetap presiden terbaik",
            "idola kami bapak jokowi",
            "ane bapak ini ngapain",
            "firasat gua wanita itu akan bergerak",
            "pak presiden ini seperti ayah saya sendiri ayah saya sendiri",
            "bapak gw yg pensiunan pns",
            "mnurut sya sma aja smuanya",
            "gw smp check google",
        ]:
            assert p.self_statements(text) == [], text

    def test_peran_dengan_penegas_diterima(self) -> None:
        assert p.self_statements("saya seorang ibu tua yg miskin")[0].gender == "P"
        assert p.self_statements("saya sbg ibu nangis lihatnya")[0].gender == "P"
        assert p.self_statements("saya bapak dua anak")[0].gender == "L"
        assert p.self_statements("kami emak yang terbantu")[0].gender == "P"
        assert p.self_statements("aku cewek tiba harus hidup sendiri")[0].gender == "P"
        assert p.self_statements("saya masih sma kelas 2")[0].age == "<=17"

    def test_lulusan_sma_bukan_anak_sma(self) -> None:
        assert p.self_statements("saya lulusan SMA tapi paham") == []

    def test_ibu_rumah_tangga_satu_pernyataan(self) -> None:
        sts = p.self_statements("saya ibu rumah tangga")
        assert len(sts) == 1 and sts[0].gender == "P"

    def test_age_band(self) -> None:
        assert p.age_band(17) == "<=17"
        assert p.age_band(18) == "18-24"
        assert p.age_band(34) == "25-34"
        assert p.age_band(44) == "35-44"
        assert p.age_band(45) == "45+"
        assert p.age_band(5) is None
        assert p.age_band(99) is None


class TestMinat:
    def test_penanda_per_kategori(self) -> None:
        m = p.interest_markers("habis mabar terus ngopi sama teman")
        assert m == {"gim": "mabar", "kuliner": "ngopi"}

    def test_kata_topik_umum_tidak_jadi_penanda(self) -> None:
        assert p.interest_markers("harga bensin pertalite naik, sekolah anak mahal") == {}

    def test_kata_topik_dikecualikan(self) -> None:
        assert p.interest_markers("martabak manis enak", exclude={"martabak"}) == {}
        prof = p.Profiler(exclude=["Martabak", " "])
        prof.add([("a", "martabak lagi"), ("a", "martabak terus")])
        assert prof.marked_authors() == []

    def test_keyakinan(self) -> None:
        assert p.interest_confidence(1) < p.MIN_CONFIDENCE
        assert p.interest_confidence(2) >= p.MIN_CONFIDENCE
        assert p.interest_confidence(50) == 0.9


class TestProfiler:
    def test_agregat_dan_ambang(self) -> None:
        prof = p.Profiler()
        prof.add(
            [
                ("a", "saya ibu rumah tangga, mabar tiap malam"),
                ("a", "game ini seru"),
                ("b", "gue cowok, umur gue 20 tahun"),
                ("c", "komentar biasa saja"),
                (None, "tanpa akun tidak dihitung"),
            ]
        )
        assert sorted(prof.marked_authors()) == ["a", "b"]
        stats = prof.result(n_accounts=3, sentiment={"a": (0.0, 2), "b": (0.2, 1)})
        assert stats.n_accounts == 3
        assert stats.n_comments == 4
        assert stats.gender == {"L": 1, "P": 1}
        assert stats.age["18-24"] == 1
        assert stats.pyramid == {("18-24", "L"): 1}
        assert stats.interests == {"gim": 1}
        assert stats.interests_by_gender["P"] == {"gim": 1}
        seg = {s.segment: s for s in stats.sentiment}
        assert seg["gender:P"].mean == 0.0 and seg["gender:P"].scored == 2
        assert seg["minat:gim"].accounts == 1
        assert ("saya … ibu rumah tangga", 1) in stats.evidence["gender:P"]

    def test_satu_komentar_minat_tidak_cukup(self) -> None:
        prof = p.Profiler()
        prof.add([("a", "mabar yuk")])
        assert prof.result(n_accounts=1).interests == {}
        assert prof.profiles()["a"].interests == ()

    def test_pernyataan_bertentangan_jadi_null(self) -> None:
        prof = p.Profiler()
        prof.add([("a", "saya ibu"), ("a", "saya bapak")])
        assert prof.profiles()["a"].gender.value is None
        assert prof.result(n_accounts=1).gender == {"L": 0, "P": 0}

    def test_dua_pernyataan_menaikkan_keyakinan(self) -> None:
        prof = p.Profiler()
        prof.add([("a", "saya ibu")])
        assert prof.profiles()["a"].gender.confidence == p.GENDER_CONFIDENCE_ONE
        prof.add([("a", "sebagai ibu saya sedih"), ("a", "aku seorang ibu")])
        assert prof.profiles()["a"].gender.confidence == p.GENDER_CONFIDENCE_MANY

    def test_umur_tidak_sepakat_jadi_null(self) -> None:
        prof = p.Profiler()
        prof.add([("a", "saya anak SMP"), ("a", "umur saya 50 tahun")])
        assert prof.profiles()["a"].age.value is None

    def test_tidak_ada_kategori_terlarang(self) -> None:
        banned = {"agama", "etnis", "suku", "politik", "kesehatan", "orientasi"}
        assert not banned & set(p.INTERESTS)
