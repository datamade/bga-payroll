.INTERMEDIATE : illinois_places_tigerlines.zip

clean :
	rm -rf illinois_places_tigerlines

illinois_places_tigerlines.zip :
	wget -O $@ https://www2.census.gov/geo/tiger/TIGER2017/PLACE/tl_2017_17_place.zip

illinois_places_tigerlines : illinois_places_tigerlines.zip
	unzip -d $@ $<

illinois_places : illinois_places_tigerlines/
	psql -d $(PG_DB) -c "\d $@" > /dev/null 2>&1 || ( \
		shp2pgsql -I $</tl_2017_17_place.shp illinois_places bga_payroll | \
		psql -d bga_payroll
	)