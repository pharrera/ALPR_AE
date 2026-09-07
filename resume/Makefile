CC = lualatex
SRC = nisandre-stewart-resume.tex
PDF = $(SRC:.tex=.pdf)

.PHONY: all clean

all: $(PDF)

$(PDF): $(SRC) awesome-cv.cls
	$(CC) -interaction=nonstopmode $(SRC)

clean:
	rm -f *.aux *.log *.out *.fdb_latexmk *.fls
