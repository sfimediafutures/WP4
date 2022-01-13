#
# Makefile for Latex stuff
#

PACKAGE=2021-Dynamic_aspect_ratio


PDF = $(PACKAGE).pdf

all:  ${PDF}

%.pdf:  %.tex
	pdflatex $<
	- bibtex $*
	pdflatex $<
	- makeindex -s gind.ist -o $*.ind $*.idx
	- makeindex -s gglo.ist -o $*.gls $*.glo
	pdflatex $<
	while ( grep -q '^LaTeX Warning: Label(s) may have changed' $*.log) \
	do pdflatex $<; done

%.cls:   %.ins %.dtx
	pdflatex $<


.PRECIOUS:  $(PACKAGE).cfg $(PACKAGE).cls

docclean:
	$(RM)  *.log *.aux \
	*.cfg *.glo *.idx *.toc \
	*.ilg *.ind *.out *.lof \
	*.lot *.bbl *.blg *.gls *.cut *.hd \
	*.dvi *.ps *.thm *.tgz *.zip *.rpi


clean: docclean
	$(RM)  $(PACKAGE).cls

distclean: clean
	$(RM) $(PACKAGE).pdf
