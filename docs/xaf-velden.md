# XAF-velden: wat betekent wat, en in welke versie

Vindplaats voor alles op deze pagina: **XMLAuditfile Financieel 4.0.3**, de
functionele hiërarchie (`XMLAuditfileFinancieel_4.0_FunHie.pdf`) en het
revisiedocument naar 3.2 (`XMLAuditfileXAF_4.0_met_revisie_naar_XAF_3.2.pdf`),
te downloaden bij de Belastingdienst/ODB:
<https://odb.belastingdienst.nl/documentatie/xml-auditfile-financieel-xaf-4-0-3/>.
De XSD van XAF 3.2 staat op <http://www.auditfiles.nl/XAF/3.2>.
Geraadpleegd op 2 september 2026.

Deze pagina bestaat omdat dezelfde tagnaam in twee versies iets anders kan
betekenen, en omdat een veld dat in de specificatie bestaat niet hetzelfde is als
een veld dat gevuld is. Beide fouten zijn hier gemaakt en gecorrigeerd.

## Versies

| Versie | Namespace | Bijzonderheden |
|---|---|---|
| 3.2 | `http://www.auditfiles.nl/XAF/3.2` | Ongeveer 250 velden. Heeft een optionele subadministratie. RGS alleen via `leadReference`. |
| 4.0 | `http://www.odb.belastingdienst.nl/Belastingdienst/BCPP/1.1/structures/XmlauditfileXAF_4.0` | Ongeveer 90 velden. Subadministratie geschrapt. `RGScode` rechtstreeks. |

Vanaf **1 januari 2027** accepteert de Belastingdienst uitsluitend XAF 4.0 voor
aanlevering. Voor analyse blijft 3.2 relevant: die versie is rijker, en
historische dossiers blijven bestaan.

## Datums, en waarom ze door elkaar worden gehaald

| Tag | 3.2 | 4.0 |
|---|---|---|
| `trDt` | boekingsdatum: wanneer de transactie in het systeem is verwerkt | idem |
| `effDate` | **mutatiedatum**: wanneer het evenement plaatsvond dat tot de journaalpost leidde | **factuurdatum**: wanneer de factuur is uitgereikt |
| `settDate` | bestaat niet | **leverdatum** of de datum van een vooruitbetaling; een factuurvereiste voor de btw |
| `invDt` | factuurdatum, alleen in de subadministratie | bestaat niet |
| `invDueDt` | **vervaldatum**, alleen in de subadministratie | bestaat niet |

Geen van `trDt`, `effDate` en `settDate` is een vervaldatum. De enige echte
vervaldatum in XAF is `invDueDt`, en die bestaat alleen in 3.2.

## Dezelfde naam, andere betekenis

`opBalDesc` bestaat in beide versies en betekent iets anders:

- **3.2**: een `String999` binnen `openingBalance`, naast `opBalDate`. Een
  omschrijving van de beginbalans van het grootboek.
- **4.0**: een bedrag (`n..20,2`) binnen `customerSupplier`. Het openstaande
  bedrag per relatie bij het begin van het boekjaar, met `opBalTp` voor debet of
  credit. `clBalDesc`/`clBalTp` geven dezelfde stand aan het einde.

Wie op tagnaam telt of leest, leest in een 3.2-bestand een omschrijving als
openstaand bedrag. `_tel_blokken()` in `parsing.py` telt daarom uitsluitend
binnen `customersSuppliers`.

## Subadministratie (alleen 3.2)

Twee blokken, beide optioneel:

- `openingBalance/obSubledgers/obSubledger/obSbLine` — openstaande posten bij het
  begin van het boekjaar;
- `transactions/subledgers/subledger/sbLine` — mutaties daarin gedurende het jaar,
  met `jrnID`, `trNr` en `trLineNr` als koppeling naar de grootboekboeking.

Velden die ertoe doen: `custSupID`, `invRef`, `invDt`, `invDueDt`, `matchKeyID`,
`invTp`, `mutTp` (I, P of Z) en `sbType` (CS, CU, SU of ZZ).

De Belastingdienst heeft deze blokken in 4.0 geschrapt met als onderbouwing dat
veel 3.2-velden in de praktijk niet of onvolledig werden gevuld. Onze eigen
metingen bevestigen dat: in de beschikbare 3.2-bestanden is de subadministratie
volledig leeg.

## Bewijsniveaus voor openstaande posten

`capability.py` bepaalt per bestand het hoogste niveau dat de gegevens dragen:

| Niveau | Voorwaarde | Wat het toelaat |
|---|---|---|
| 1 | subadministratie mét `invDueDt` | ouderdom en achterstalligheid zonder aanname |
| 2 | subadministratie zonder vervaldatum | openstaande posten, ouderdom vanaf de factuurdatum |
| 3 | 4.0 met `clBalDesc` gevuld | eindstand per relatie, geen factuurlijst, geen ouderdom |
| 4 | grootboekregels met `invRef` en `custSupID` op **beide** zijden | reconstructie; ouderdom vanaf de boekingsdatum, achterstalligheid alleen onder een opgegeven betalingstermijn |
| 0 | geen van bovenstaande | geen openstaande-postenanalyse |

Niveau 4 vraagt uitdrukkelijk dat de factuurreferentie ook op de betaling staat.
Staat zij alleen op de factuur, dan blijft bij salderen per referentie vrijwel
elke factuur van het jaar als openstaand staan. Dat oogt volledig en is onwaar,
en het is precies wat de beschikbare bestanden laten zien: de referentie staat
daar op de factuurzijde en niet op de betaalzijde, waardoor 14% tot 22% van de
facturen een tegenboeking heeft.

## Debet en credit

`amntTp` is `D` of `C`. De omrekening naar een getekend bedrag is
`getekend = -amnt` bij `C` en `amnt` bij `D`; het teken van het bedrag zelf telt
gewoon mee. Zie de moduletoelichting van `parsing.py` voor de onderbouwing tegen
de controletotalen.

## RGS

XAF 4.0 levert `RGScode` per rekening. XAF 3.2 kent dat element niet en heeft
hooguit `leadReference`, wat geen gegarandeerde RGS-code is. De herkomst staat in
de kolom `RGSbron`, zodat zichtbaar blijft hoe hard de indeling is.
