VPATH=data

golf-amendment.csv : 2017-actual-pt-1.csv
	csvgrep -c employer,department -r '^Golf$$' -a $< > $@
