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
binnen `customersSuppliers`, en `_parse_relations()` leest de bedragen alleen
wanneer de namespace 4.0 is. Ze komen getekend in het model terecht (debet
positief, credit negatief) als `openstaand_begin` en `openstaand_eind`; bij 3.2
blijven die kolommen leeg. `relatiesaldi.py` zet ze tegenover het saldo van de
debiteuren- en de crediteurenrekening.

## Subadministratie (alleen 3.2)

Twee blokken, beide optioneel:

- `openingBalance/obSubledgers/obSubledger/obSbLine` — openstaande posten bij het
  begin van het boekjaar;
- `transactions/subledgers/subledger/sbLine` — mutaties daarin gedurende het jaar.

Boven de regels staat per subadministratie een `obSubledger` of `subledger` met
`sbType` (verplicht), `sbDesc`, en de eigen controletotalen `linesCount`,
`totalDebit` en `totalCredit`. `parsing.py` leest die totalen mee en zet ze naast
wat er werkelijk is gelezen, zodat een onvolledig ingelezen blok opvalt.

### De rekening staat niet op de regel

Dit is de valkuil van deze blokken. Geen van beide regelsoorten heeft een
`accID`. De rekening volgt uit een verwijzing:

| Regel | Verwijzing | Naar |
|---|---|---|
| `obSbLine` | `obLineNr` | het `nr` van een `obLine` in de beginbalans |
| `sbLine` | `jrnID`, `trNr`, `trLineNr` | de `trLine` van de grootboekboeking |

Alleen `jrnID` heeft in de XSD een `keyref`; `trNr` en `trLineNr` hebben er geen,
en `obLineNr` ook niet. De verwijzing is dus een afspraak en geen garantie.
`_parse_subledgers()` lost haar op en legt in de kolom `koppeling` vast hoe dat
is gegaan: `obLineNr`, `jrnID/trNr/trLineNr`, `niet gevonden` of
`sleutel niet eenduidig`. Dat laatste hoort erbij omdat een pakket hetzelfde
transactienummer opnieuw kan gebruiken; wijzen twee boekingen met dezelfde
sleutel naar verschillende rekeningen, dan blijft de rekening leeg in plaats van
dat de eerste wordt gepakt.

### Velden, in de volgorde van de XSD

De XSD schrijft een `sequence` voor, dus de volgorde staat vast. Verplicht zijn
`nr`, `amnt` en `amntTp`, plus de verwijzing: `obLineNr` bij `obSbLine` en
`jrnID`, `trNr` en `trLineNr` bij `sbLine`.

`obSbLine`: `nr`, `obLineNr`, `desc`, `amnt`, `amntTp`, `docRef`, `recRef`,
`matchKeyID`, `custSupID`, `invRef`, `invPurSalTp`, `invTp`, `invDt`,
`invDueDt`, `mutTp`, `costID`, `prodID`, `projID`, `artGrpID`, `qntityID`,
`qntity`.

`sbLine`: `nr`, `jrnID`, `trNr`, `trLineNr`, daarna dezelfde reeks, met aan het
eind nog een eigen `vat`-blok (0 tot 99 keer) en een `currency`-blok. Die twee
blijven buiten het model: de btw-analyse werkt op de grootboekregels, en de
velden over kostenplaatsen, projecten en voorraad gaan niet over openstaande
posten.

### Codelijsten

| Veld | Waarden | Betekenis |
|---|---|---|
| `amntTp`, `invTp` | D, C | debet of credit |
| `invPurSalTp` | P, S | inkoop of verkoop |
| `sbType` | CS, CU, SU, ZZ | **niet vastgesteld** |
| `mutTp` | I, P, Z | **niet vastgesteld** |

De XSD geeft voor `sbType` en `mutTp` alleen de toegestane waarden en geen
omschrijving, en de Invantive-documentatie van het 3.2-datamodel noemt ze
"Subledger Type" en "Mutation Type" zonder waardelijst. Er is een aannemelijke
lezing (`CU` klant, `SU` leverancier, `CS` beide, `ZZ` overig, naar analogie van
`custSupTp` met B, C, O en S; `I` factuur, `P` betaling), maar die is niet uit
een gezaghebbende bron te herleiden. De tool geeft beide codes daarom
onveranderd door en leidt er niets uit af. **Open punt**: vaststellen wat deze
codes betekenen aan de hand van de functionele documentatie van XAF 3.2.

### Wat de bestanden in de praktijk laten zien

De Belastingdienst heeft deze blokken in 4.0 geschrapt met als onderbouwing dat
veel 3.2-velden in de praktijk niet of onvolledig werden gevuld. Onze eigen
metingen bevestigen dat: in de beschikbare 3.2-bestanden is de subadministratie
volledig leeg. Het synthetische 3.2-bestand van `demo.py` vult haar wél, zodat
het hoogste bewijsniveau zonder klantdata te testen is.

### Herkomst van deze paragraaf

De officiële vindplaats `http://www.auditfiles.nl/XAF/3.2` is niet meer
bereikbaar; het domein lost sinds 2 september 2026 niet op. De structuur
hierboven is gelezen uit `XmlAuditfileFinancieel3.2.xsd` met
`targetNamespace="http://www.auditfiles.nl/XAF/3.2"`, via de spiegel
<https://github.com/BananaAccounting/Netherlands/blob/master/Auditfile_v3.2/XmlAuditfileFinancieel3.2.xsd>.
Het door `demo.py` gegenereerde 3.2-bestand valideert tegen die XSD, inclusief
beide subadministratieblokken. De XSD staat niet in deze repository; wie de
validatie wil herhalen haalt hem op en gebruikt `lxml.etree.XMLSchema`.

## Bewijsniveaus voor openstaande posten

`capability.py` bepaalt per bestand het hoogste niveau dat de gegevens dragen.
De subadministratie wordt daarvoor uit `Auditfile.subadministratie` gelezen, dus
uit wat er werkelijk is ingelezen en niet uit een aparte telling van elementen:

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
