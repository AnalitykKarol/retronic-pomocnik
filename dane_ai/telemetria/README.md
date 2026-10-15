# Telemetria do treningu lokalnego modelu

Kopie `logi/telemetria-RRRRMMDD.jsonl` (w repo ignorowane) spakowane gzipem, żeby drugi komputer mógł trenować.

- `stacjonarka-dev/`: z katalogu deweloperskiego (~/Games/Retronic/pomocnik/logi), 11-15.10.
- `stacjonarka-stabilny/`: z bota na żywo (~/Games/Retronic/pomocnik-stabilny/logi), 14-15.10. Plik 15.10 obejmuje całą sesję do 20:36 (śmierć od PK o ok. 20:35).

Użycie: rozpakuj do osobnego katalogu i wskaż go zbiorowi, np.
`mkdir -p /tmp/tel && for f in dane_ai/telemetria/*/*.gz; do d=/tmp/tel/$(basename $(dirname $f)); mkdir -p $d; gunzip -c $f > $d/$(basename $f .gz); done`
Pliki z tą samą datą w dwóch podkatalogach to różne procesy (pole `pid`/`sesja`), nie duplikaty.

`dane_ai/zdarzenia/`: wycinki logu bota (mozg) wokół ważnych zdarzeń, np. śmierć od graczy PK 15.10 20:35 (opis: dane_tibia/SPEC_obrona_pk_1015.md).
