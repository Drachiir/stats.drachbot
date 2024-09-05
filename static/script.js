document.addEventListener("DOMContentLoaded", function () {
    initializeTableSorting("myTable");
    initializeTableSorting("myTable1");
    initializeTableSorting("myTable2");
    initializeTableSorting("myTable3");
    initializeTableSorting("myTable4");

    function initializeTableSorting(tableId) {
        const table = document.getElementById(tableId);
        if (!table) {
            return;
        }

        const headers = table.querySelectorAll("tbody th");

        function addHeaderClass(header) {
            if (header.innerText.startsWith("Games") && header.parentNode.rowIndex === 1) {
                header.classList.add("desc");
            }
            if (!header.innerText.startsWith("Best") && header.parentNode.rowIndex > 1) {
                if (header.innerText.startsWith("Games") && header.parentNode.rowIndex === 3) {
                    header.classList.add("desc");
                } else if (header.innerText.startsWith("Endrate") && header.parentNode.rowIndex === 2) {
                    header.classList.add("desc");
                } else {
                    header.classList.add("asc");
                }
            }
        }

        headers.forEach(h => addHeaderClass(h));
        const tbody = table.querySelector("tbody");

        function transposeTable() {
            const rows = Array.from(tbody.rows);
            const transposed = rows[0].cells.length - 1; // excluding header column

            const newRows = [];
            for (let i = 0; i < transposed; i++) {
                const newRow = [];
                for (let row of rows) {
                    const cell = row.cells[i + 1]; // +1 to skip header column
                    newRow.push(cell ? cell.outerHTML : "");
                }
                newRows.push(newRow);
            }

            return newRows;
        }

        // Function to sort the table based on transposed rows
        function sortTable(columnIndex, asc = true) {
            const newRows = transposeTable();
            const sortedRows = newRows.sort((a, b) => {
                const aText = a[columnIndex].replace(/<[^>]*>?/gm, '').trim();
                const bText = b[columnIndex].replace(/<[^>]*>?/gm, '').trim();

                // Check if the column has 'Tier' values and apply custom sort order
                const tierOrder = ['D', 'C', 'B', 'A', 'S', 'S+'];
                const aTierIndex = tierOrder.indexOf(aText);
                const bTierIndex = tierOrder.indexOf(bText);

                // If both are tier values, use custom order
                if (aTierIndex !== -1 && bTierIndex !== -1) {
                    return asc ? aTierIndex - bTierIndex : bTierIndex - aTierIndex;
                }

                // Otherwise, apply default numeric sorting for non-tier values
                const aNumber = parseFloat(aText);
                const bNumber = parseFloat(bText);

                if (!isNaN(aNumber) && !isNaN(bNumber)) {
                    return asc ? aNumber - bNumber : bNumber - aNumber;
                }

                return 0;
            });

            // Apply sorted rows to the table
            sortedRows.forEach((row, index) => {
                for (let i = 0; i < row.length; i++) {
                    tbody.rows[i].cells[index + 1].outerHTML = row[i]; // +1 to skip header column
                }
            });
        }

        // Attach click event listener to header cells
        headers.forEach((header, index) => {
            if (!header.innerText.startsWith("Best") && index > 0) {
                header.addEventListener("click", function () {
                    const asc = !header.classList.contains("asc");
                    header.classList.toggle("asc", asc);
                    header.classList.toggle("desc", !asc);
                    sortTable(index, asc);
                });
            }
        });

        // Initial sorting by "Tier" column in descending order
        // const tierHeaderIndex = Array.from(headers).findIndex(header => header.innerText.startsWith("Tier"));
        // if (tierHeaderIndex !== -1) {
        //     sortTable(tierHeaderIndex, false); // False for descending order
        //     headers[tierHeaderIndex].classList.add("desc"); // Mark header as sorted descending
        // }
    }
});



function myFunction() {
  document.getElementById("myDropdown").classList.toggle("show");
}

function filterFunction() {
  const input = document.getElementById("myInput");
  const filter = input.value.toUpperCase();
  const div = document.getElementById("myDropdown");
  const a = div.getElementsByTagName("a");
  for (let i = 0; i < a.length; i++) {
    txtValue = a[i].textContent || a[i].innerText;
    if (txtValue.toUpperCase().indexOf(filter) > -1) {
      a[i].style.display = "";
    } else {
      a[i].style.display = "none";
    }
  }
}

var table = document.getElementById('myTable');
var tbody = table.getElementsByTagName('tbody')[0];
var cells = tbody.getElementsByTagName('td');

for (var i=0, len=cells.length; i<len; i++){
    const value = cells[i].innerHTML;
    if (value === "S+"){
        cells[i].style.color = 'Yellow';
    }
    else if (value === "S"){
        cells[i].style.color = 'Gold';
    }
    else if (value === "A"){
        cells[i].style.color = 'GreenYellow';
    }
    else if (value === "B"){
        cells[i].style.color = 'MediumSeaGreen';
    }
    else if (value === "C"){
        cells[i].style.color = 'DarkOrange';
    }
    else if (value === "D"){
        cells[i].style.color = 'Red';
    }
}
