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

        const headers = table.querySelectorAll("th");
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
                const aText = parseFloat(a[columnIndex].replace(/<[^>]*>?/gm, ''));
                const bText = parseFloat(b[columnIndex].replace(/<[^>]*>?/gm, ''));

                return asc ? aText - bText : bText - aText;
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
            header.addEventListener("click", function () {
                const asc = !header.classList.contains("asc");
                headers.forEach(h => h.classList.remove("asc", "desc"));
                header.classList.toggle("asc", asc);
                header.classList.toggle("desc", !asc);
                sortTable(index, asc); // -1 to skip header column
            });
        });
    }
});
