"""Wat laat dit auditfile toe, en wat niet?

Een auditfile is geen vaste hoeveelheid gegevens. XAF 3.2 en 4.0 verschillen
inhoudelijk, en binnen één versie is bijna alles optioneel: of een gegeven er
staat, bepaalt het boekhoudpakket en soms de instelling van de export. Twee
bestanden van dezelfde onderneming over twee jaren kunnen dus verschillende
analyses toelaten.

Zonder deze laag zou de tool een analyse tonen die op te weinig gegevens rust.
Bij openstaande posten is dat gevaarlijk: een reconstructie uit boekingsregels
kan er volledig uitzien terwijl bijna elke factuur onterecht als openstaand
verschijnt. Deze module stelt daarom eerst vast wat er is, en vertaalt dat naar
het niveau van bewijs dat een uitspraak toelaat.

Wat er per versie te verwachten valt
------------------------------------
``XAF 3.2``
    Heeft een optionele subadministratie: ``obSbLine`` voor de openstaande
    posten bij het begin van het boekjaar en ``sbLine`` voor de mutaties daarin.
    Daarin kunnen ``invDt`` (factuurdatum), ``invDueDt`` (vervaldatum) en
    ``matchKeyID`` (afletterkenmerk) staan. Dit is de rijkste bron, mits gevuld.
``XAF 4.0``
    Heeft die blokken niet meer; dat is onderdeel van de reductie van ongeveer
    250 naar 90 velden. In plaats daarvan staat per relatie een openstaand
    bedrag bij begin en einde van het boekjaar (``opBalDesc``/``clBalDesc``).
    Er is geen vervaldatum. ``settDate`` lijkt erop maar is de leverdatum of de
    datum van een vooruitbetaling.

Vindplaats: XMLAuditfile Financieel 4.0.3, functionele hiërarchie en het
revisiedocument naar XAF 3.2, Belastingdienst/ODB. Zie ``docs/xaf-velden.md``.
"""
from __future__ import annotations

import pandas as pd

from .controls import RELATIEREKENINGEN, _selecteer
from .model import Auditfile

# --- Niveaus van bewijs voor openstaande posten -----------------------------

NIVEAU_GEEN = 0
NIVEAU_RECONSTRUCTIE = 4
NIVEAU_RELATIESALDO = 3
NIVEAU_SUBADMINISTRATIE = 2
NIVEAU_VERVALDATUM = 1

NIVEAU_NAAM: dict[int, str] = {
    NIVEAU_VERVALDATUM: "Subadministratie met vervaldatum",
    NIVEAU_SUBADMINISTRATIE: "Subadministratie zonder vervaldatum",
    NIVEAU_RELATIESALDO: "Openstaand bedrag per relatie",
    NIVEAU_RECONSTRUCTIE: "Reconstructie uit boekingsregels",
    NIVEAU_GEEN: "Geen openstaande-postenanalyse mogelijk",
}

# Een reconstructie uit boekingsregels werkt alleen wanneer de factuurreferentie
# op beide zijden van de post staat: op de factuur én op de betaling. Staat hij
# alleen op de factuur, dan levert salderen per referentie niets af en verschijnt
# elke factuur van het jaar als openstaand. Deze grens is een werkafspraak en
# geen norm; het gemeten percentage staat altijd in de uitkomst, zodat de
# gebruiker zelf kan wegen.
MINIMALE_KOPPELING_PCT = 50.0

# Onder deze dekking is een reconstructie niet meer dan een steekproef.
MINIMALE_REFERENTIEDEKKING_PCT = 50.0


def _pct(deel: float, geheel: float) -> float:
    return float(deel) / float(geheel) * 100.0 if geheel else float("nan")


# --- Wat zit er in het bestand? ---------------------------------------------

PROFIEL_COLUMNS = ["gegeven", "aanwezig", "aantal", "dekking_pct", "toelichting"]


def build_bestandsprofiel(af: Auditfile) -> pd.DataFrame:
    """Per gegevensblok: zit het erin, en hoe volledig?

    De dekking is bewust een percentage van het aantal regels of rekeningen waar
    het gegeven op zou kunnen staan, niet van het bestand als geheel. Een
    factuurreferentie op 40% van alle boekingsregels zegt niets; op 40% van de
    debiteurenregels zegt het alles.
    """
    blokken = af.blokken or {}
    regels = len(af.lines)
    rekeningen = len(af.accounts)
    met_rgs = int((af.accounts["RGScode"].astype(str).str.strip() != "").sum()) if rekeningen else 0
    rgs_bronnen = (
        sorted({bron for bron in af.accounts["RGSbron"].astype(str) if bron}) if rekeningen else []
    )
    met_relatie = (
        int((af.lines["line_custSupID"].astype(str).str.strip() != "").sum()) if regels else 0
    )
    met_factuur = (
        int((af.lines["line_invRef"].astype(str).str.strip() != "").sum()) if regels else 0
    )
    met_btw = (
        int(((af.lines["vat_vatID"] != "") | (af.lines["line_vatID"] != "")).sum()) if regels else 0
    )

    rijen = [
        {
            "gegeven": "Grootboekrekeningen",
            "aantal": rekeningen,
            "dekking_pct": float("nan"),
            "toelichting": "Het rekeningschema; de basis voor elke indeling.",
        },
        {
            "gegeven": "RGS-codes",
            "aantal": met_rgs,
            "dekking_pct": _pct(met_rgs, rekeningen),
            "toelichting": "Aandeel van de rekeningen met een code"
            + (f", herkomst {' en '.join(rgs_bronnen)}" if rgs_bronnen else "")
            + ". Zonder code valt de indeling terug op de omschrijving.",
        },
        {
            "gegeven": "Beginbalans grootboek",
            "aantal": len(af.opening_balance),
            "dekking_pct": float("nan"),
            "toelichting": "Nodig voor eindsaldi en voor de aansluiting op vorig jaar.",
        },
        {
            "gegeven": "Boekingsregels",
            "aantal": regels,
            "dekking_pct": float("nan"),
            "toelichting": "De mutaties van het boekjaar.",
        },
        {
            "gegeven": "Btw-code op de boekingsregel",
            "aantal": met_btw,
            "dekking_pct": _pct(met_btw, regels),
            "toelichting": "Bepaalt of de btw-analyse en de rondrekening mogelijk zijn.",
        },
        {
            "gegeven": "Relatietabel",
            "aantal": len(af.relations),
            "dekking_pct": float("nan"),
            "toelichting": "Namen bij de relatie-id's. Ontbreekt die, dan werkt de "
            "analyse nog wel maar zonder namen.",
        },
        {
            "gegeven": "Relatie-id op de boekingsregel",
            "aantal": met_relatie,
            "dekking_pct": _pct(met_relatie, regels),
            "toelichting": "Nodig om mutaties aan een debiteur of crediteur toe te wijzen.",
        },
        {
            "gegeven": "Factuurreferentie op de boekingsregel",
            "aantal": met_factuur,
            "dekking_pct": _pct(met_factuur, regels),
            "toelichting": "Nodig om boekingen tot facturen te groeperen. Zie de "
            "dekking op de relatierekeningen hieronder; die telt, niet dit totaal.",
        },
        {
            "gegeven": "Subadministratie beginbalans (obSbLine, alleen 3.2)",
            "aantal": blokken.get("obSbLine", 0),
            "dekking_pct": float("nan"),
            "toelichting": "Openstaande posten bij het begin van het boekjaar.",
        },
        {
            "gegeven": "Subadministratie mutaties (sbLine, alleen 3.2)",
            "aantal": blokken.get("sbLine", 0),
            "dekking_pct": float("nan"),
            "toelichting": "Mutaties in de subadministratie gedurende het boekjaar.",
        },
        {
            "gegeven": "Vervaldatum in de subadministratie (invDueDt)",
            "aantal": blokken.get("obSbLine_invDueDt", 0) + blokken.get("sbLine_invDueDt", 0),
            "dekking_pct": float("nan"),
            "toelichting": "Het enige echte vervaldatumveld in XAF. Bestaat niet in 4.0.",
        },
        {
            "gegeven": "Afletterkenmerk (matchKeyID)",
            "aantal": blokken.get("obSbLine_matchKeyID", 0) + blokken.get("sbLine_matchKeyID", 0),
            "dekking_pct": float("nan"),
            "toelichting": "Koppelt betaling aan factuur zonder aanname. Bestaat niet in 4.0.",
        },
        {
            "gegeven": "Openstaand bedrag per relatie (clBalDesc, alleen 4.0)",
            "aantal": blokken.get("relatie_clBalDesc", 0),
            "dekking_pct": _pct(blokken.get("relatie_clBalDesc", 0), len(af.relations)),
            "toelichting": "Eindstand per debiteur en crediteur, rechtstreeks uit het bestand.",
        },
        {
            "gegeven": "Perioden",
            "aantal": len(af.periods),
            "dekking_pct": float("nan"),
            "toelichting": "Nodig voor de controles per periode.",
        },
    ]
    profiel = pd.DataFrame(rijen)
    profiel["aanwezig"] = profiel["aantal"] > 0
    return profiel[PROFIEL_COLUMNS]


# --- Dekking op de relatierekeningen ----------------------------------------

DEKKING_COLUMNS = [
    "soort",
    "methode",
    "rekeningen",
    "regels",
    "met_relatie_pct",
    "met_factuurreferentie_pct",
    "facturen",
    "gekoppeld_pct",
    "conclusie",
]


def build_relatiedekking(af: Auditfile) -> pd.DataFrame:
    """Hoe bruikbaar zijn de factuurreferenties op de relatierekeningen?

    Het percentage regels met een referentie is niet genoeg. Beslissend is of de
    referentie op beide zijden staat: alleen dan is per factuur te salderen tot
    een openstaand bedrag. Staat de referentie alleen op de factuur en niet op de
    betaling, dan blijft elke factuur als openstaand staan en is de uitkomst
    onbruikbaar, hoe volledig zij ook oogt.
    """
    if af.lines.empty or "line_custSupID" not in af.lines.columns:
        return pd.DataFrame(columns=DEKKING_COLUMNS)

    rijen = []
    for soort, (rgs_prefix, patroon) in RELATIEREKENINGEN.items():
        masker, methode = _selecteer(af.lines, rgs_prefix, patroon, rekeningtype="B")
        regels = af.lines[masker]
        if regels.empty:
            rijen.append(
                {
                    "soort": soort,
                    "methode": methode,
                    "rekeningen": 0,
                    "regels": 0,
                    "met_relatie_pct": float("nan"),
                    "met_factuurreferentie_pct": float("nan"),
                    "facturen": 0,
                    "gekoppeld_pct": float("nan"),
                    "conclusie": f"Geen {soort}enrekening herkend.",
                }
            )
            continue

        met_relatie = regels["line_custSupID"].astype(str).str.strip() != ""
        met_factuur = regels["line_invRef"].astype(str).str.strip() != ""
        toewijsbaar = regels[met_relatie & met_factuur]

        facturen = 0
        gekoppeld = 0
        if not toewijsbaar.empty:
            groepen = toewijsbaar.groupby(
                [
                    toewijsbaar["line_custSupID"].astype(str),
                    toewijsbaar["line_invRef"].astype(str),
                ]
            )
            facturen = groepen.ngroups
            gekoppeld = sum(
                1
                for _, groep in groepen
                if (groep["bedrag"] > 0).any() and (groep["bedrag"] < 0).any()
            )

        referentie_pct = _pct(int(met_factuur.sum()), len(regels))
        gekoppeld_pct = _pct(gekoppeld, facturen)
        rijen.append(
            {
                "soort": soort,
                "methode": methode,
                "rekeningen": int(regels["line_accID"].nunique()),
                "regels": len(regels),
                "met_relatie_pct": _pct(int(met_relatie.sum()), len(regels)),
                "met_factuurreferentie_pct": referentie_pct,
                "facturen": facturen,
                "gekoppeld_pct": gekoppeld_pct,
                "conclusie": _dekkingsconclusie(referentie_pct, gekoppeld_pct),
            }
        )
    return pd.DataFrame(rijen, columns=DEKKING_COLUMNS)


def _dekkingsconclusie(referentie_pct: float, gekoppeld_pct: float) -> str:
    if pd.isna(referentie_pct) or referentie_pct < 0.005:
        return "Geen factuurreferenties; boekingen zijn niet tot facturen te groeperen."
    if pd.isna(gekoppeld_pct) or gekoppeld_pct < MINIMALE_KOPPELING_PCT:
        return (
            f"De factuurreferentie staat vrijwel alleen op de factuurzijde: slechts "
            f"{0.0 if pd.isna(gekoppeld_pct) else gekoppeld_pct:.0f}% van de facturen heeft "
            "ook een boeking aan de andere kant. Salderen per referentie zou bijna elke "
            "factuur als openstaand tonen."
        )
    if referentie_pct < MINIMALE_REFERENTIEDEKKING_PCT:
        return (
            f"Referenties op {referentie_pct:.0f}% van de regels. Een reconstructie dekt "
            "dan maar een deel van de post."
        )
    return "Referenties staan op beide zijden; een reconstructie is bruikbaar."


# --- Wat laat dit bestand toe? ----------------------------------------------


def openstaande_posten_niveau(af: Auditfile) -> tuple[int, str]:
    """Het hoogste niveau van bewijs dat dit bestand toelaat, met de reden.

    De volgorde is die van hard naar zacht. Er wordt niet gezocht naar het
    niveau dat het beste resultaat oplevert, maar naar het hoogste dat de
    gegevens werkelijk dragen.
    """
    blokken = af.blokken or {}
    subadministratie = blokken.get("obSbLine", 0) + blokken.get("sbLine", 0)
    vervaldatums = blokken.get("obSbLine_invDueDt", 0) + blokken.get("sbLine_invDueDt", 0)
    relatiesaldi = blokken.get("relatie_clBalDesc", 0)

    if subadministratie and vervaldatums:
        return (
            NIVEAU_VERVALDATUM,
            f"Dit bestand bevat een subadministratie van {subadministratie} regels met "
            f"{vervaldatums} vervaldatums. Ouderdom en achterstalligheid zijn te bepalen "
            "zonder aanname.",
        )
    if subadministratie:
        return (
            NIVEAU_SUBADMINISTRATIE,
            f"Dit bestand bevat een subadministratie van {subadministratie} regels, maar "
            "zonder vervaldatum. Openstaande posten zijn te bepalen, ouderdom alleen vanaf "
            "de factuurdatum.",
        )
    if relatiesaldi:
        return (
            NIVEAU_RELATIESALDO,
            f"Dit bestand geeft voor {relatiesaldi} relatie(s) het openstaande bedrag aan "
            "het einde van het boekjaar. Dat is een eindstand per relatie, geen lijst van "
            "afzonderlijke facturen en geen ouderdom.",
        )

    dekking = build_relatiedekking(af)
    bruikbaar = (
        dekking[dekking["gekoppeld_pct"] >= MINIMALE_KOPPELING_PCT]
        if not dekking.empty
        else dekking
    )
    if not bruikbaar.empty:
        soorten = ", ".join(f"{soort}en" for soort in bruikbaar["soort"])
        return (
            NIVEAU_RECONSTRUCTIE,
            f"Er is geen subadministratie en geen openstaand bedrag per relatie. Bij "
            f"{soorten} staat de factuurreferentie wel op beide zijden, dus zijn "
            "openstaande posten te reconstrueren uit de boekingsregels. De ouderdom loopt "
            "dan vanaf de boekingsdatum en achterstalligheid alleen onder een "
            "betalingstermijn die u zelf opgeeft.",
        )

    redenen = list(dekking["conclusie"]) if not dekking.empty else []
    return (
        NIVEAU_GEEN,
        "Dit bestand laat geen openstaande-postenanalyse toe. Er is geen subadministratie "
        "(die bestaat alleen in XAF 3.2 en is hier niet gevuld), geen openstaand bedrag per "
        "relatie (alleen in XAF 4.0, hier niet gevuld) en de boekingsregels dragen te weinig "
        "koppelbare factuurreferenties. "
        + " ".join(redenen),
    )
