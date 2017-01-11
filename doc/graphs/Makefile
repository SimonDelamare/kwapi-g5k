SRC= $(wildcard *.dot)
OBJ= $(SRC:.dot=.png)

all: $(OBJ)

%.png: %.dot
	dot $^ -Tpng > $@

clean:
	rm *.png
