from app.cache import TTLCache
from app.models import GeocodeResult
from app.providers.geocoding.chain import ChainGeocoding, name_match_tier, rank_by_name


def R(name, lat=1.30, lng=103.80, src="x"):
    return GeocodeResult(name=name, address="", lat=lat, lng=lng, source=src)


class Fake:
    def __init__(self, name, results, available=True):
        self.name, self.results, self.available, self.calls = name, results, available, 0

    def search(self, q, limit=8):
        self.calls += 1
        return list(self.results)


def test_tiers_and_stable_rank():
    assert name_match_tier("Jurong Point", "JURONG POINT") == 3
    assert name_match_tier("Jurong Point", "Jurong Point Foodcourt") == 2
    assert name_match_tier("Jurong Point", "Golden Village (Gv Jurong Point)") == 1
    assert name_match_tier("Jurong Point", "Family Point Clinic") == 0
    ranked = rank_by_name("Jurong Point", [R("Family Point Clinic"), R("Gv Jurong Point"), R("Jurong Point"),
                                           R("Jurong Point", lat=1.31)])
    assert [r.name for r in ranked][:2] == ["Jurong Point", "Jurong Point"]
    assert ranked[0].lat == 1.30  # provider order kept within a tier


def test_exact_match_stops_the_chain():
    a = Fake("onemap", [R("Confucius Institute, NTU"), R("Nanyang Technological University")])
    b = Fake("photon", [R("Nanyang Technological University", lat=1.35)])
    out = ChainGeocoding([a, b]).search("Nanyang Technological University")
    assert out[0].name == "Nanyang Technological University" and b.calls == 0


def test_no_exact_match_merges_fallbacks():
    a = Fake("onemap", [R("Changi Airport Aircraft Flyover"), R("Changi Airport Bus Terminal 1")])
    b = Fake("photon", [R("Changi Airport", lat=1.357, lng=103.988, src="photon")])
    out = ChainGeocoding([a, b]).search("Changi Airport")
    assert out[0].source == "photon" and len(out) == 3


def test_unavailable_provider_skipped_and_cache_keyed_by_providers():
    cache = TTLCache(None)
    a = Fake("onemap", [R("Masjid Sultan")], available=False)
    b = Fake("photon", [R("Masjid Sultan", src="photon")])
    chain = ChainGeocoding([a, b], cache)
    assert chain.search("Masjid Sultan")[0].source == "photon" and a.calls == 0
    a.available = True  # OneMap comes back: the old cached answer must not shadow it
    assert chain.search("Masjid Sultan")[0].source == "x" and a.calls == 1


def test_acronym_keeps_provider_order():
    # OneMap knows NTU = the university; a starts-with rule must not bury it
    om = [R("Nanyang Technological University"), R("Ntu Innovation Centre"), R("Ntuc Health (Pasir Ris)")]
    assert [r.name for r in rank_by_name("NTU", om)] == [r.name for r in om]
