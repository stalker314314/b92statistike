# B92 scrapper vesti i komentara

Scrapper za statistike vesti i komentara sa sajta b92.net u 2015. godini. Ovo je set alata pisanih u Python jeziku
kojima su izvučene vesti i komentari za 2015. godinu.

## Gotove analize

Ako vas skripte ne interesuju, dobijene analize su objavljene na:

http://startit.rs/skrejpovali-smo-b92-net-nikad-necete-pogoditi-koja-vest-je-imala-247-056-minusa/

## Gotovi podaci

Ako ne želite Vi da scrape-ujete b92.net od nule, a postojeće analize nisu dovoljne,
kompletan dump baze za SQL Server se nalazi ovde:

https://portalvhds64bvg4z9qj6c7.blob.core.windows.net/bacpacs/b92-2016-1-18-22-29.bacpac
(user: sef, pass: N0vakovic)

## Hoću sve od nule

Najosnovnije uputstvo za korišćenje je (kontaktirajte me za detalje ako "ne ide"):

1. Skinite Vagrant
2. cd u clone-ovani repo i pokrenuti `vagrant up`
3. Tako se pokreće mašina koja ima setup-ovano sve za dalji rad:
   * Mongo baza
   * TOR i privoxy proxy za konekciju na TOR mrežu
   * sve python biblioteke za pokretanje svih skripti
4. ući u podignutu mašinu sa `vagrant ssh` i ući u `cd b92statistike`
5. Scrape-ovanje je 3-step proces:
   * Prvo skidamo metadata vesti sa `sudo python scrape92newsmetadata.py`
   * Onda skidamo sve tesktove vesti sa `sudo python scrapeb92news.py`
   * Na kraju skidamo komentare vesti sa `sudo python scrapeb92comments.py`
6. Ako nešto pukne, treba ispitati stack trace, ali generalno sve je idempotentno
i može da se restartuje svaka od skripti u svakom trenutku
7. Kad se sve završi, a ako Mongo nije po volji, prebacite sve u Vašu SQL bazu sa `python mongo2sql.py`
   * Morate da u samoj skripti ubacite credentials-e za Vašu bazu
   * Bazu inicijalizovati sa create-ddl.sql
8. Postoje još dve dodatne korisne skripte:
   * dump_categories.py - čita imena kategorija sa b92.net i dump-uje u log
   * title_word_statistics.py - radi histogram reči u naslovu vesti
