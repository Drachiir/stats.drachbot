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
            else if (header.innerText.startsWith("Tier") && header.parentNode.rowIndex === 1) {
                header.classList.add("asc");
            }
            if (header.innerText.startsWith("Games") && header.parentNode.rowIndex === 2) {
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
            const isTierColumn = (columnIndex === 1); // Check if the current column is the "Tier" column
            const sortedRows = newRows.sort((a, b) => {
                const aText = a[columnIndex].replace(/<[^>]*>?/gm, '').trim();
                const bText = b[columnIndex].replace(/<[^>]*>?/gm, '').trim();
                if (isTierColumn) {
                    // Retrieve the "data" attribute for both cells
                    const aDataAttr = tbody.rows[1].cells[newRows.indexOf(a) + 1].getAttribute('data') || '';
                    const bDataAttr = tbody.rows[1].cells[newRows.indexOf(b) + 1].getAttribute('data') || '';
                    // Check if the column has 'Tier' values (if applicable) or just sort by "data" attribute
                    const aTierValue = parseFloat(aDataAttr);
                    const bTierValue = parseFloat(bDataAttr);
                    if (!isNaN(aTierValue) && !isNaN(bTierValue)) {
                        return asc ? aTierValue - bTierValue : bTierValue - aTierValue;
                    }
                }
                // Fallback: Numeric sorting for non-Tier columns
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
                header.classList.add("header");
                header.addEventListener("click", function () {
                    const asc = !header.classList.contains("asc");
                    header.classList.toggle("asc", asc);
                    header.classList.toggle("desc", !asc);
                    sortTable(index, asc);
                });
            }
        });
    }
});

const statsInput = document.getElementById('statsInput');
if (statsInput) {
    statsInput.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
        }
    });
}

function showHomeDropdown() {
    const dropdown = document.getElementById("statsDropdown");
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
    document.addEventListener("click", (event) => {
        const input = document.getElementById("statsInput");
        if (!dropdown.contains(event.target) && event.target !== input) {
            dropdown.style.display = "none";
        }
    });
}

function statsFilter() {
    const input = document.getElementById("statsInput");
    const filter = input.value.toUpperCase();
    const dropdown = document.getElementById("statsDropdown");
    const ul = dropdown.getElementsByTagName("ul")[0];
    const li = ul.getElementsByTagName("li");
    let hasVisibleItems = false;
    for (let i = 0; i < li.length; i++) {
        const a = li[i].getElementsByTagName("a")[0];
        const txtValue = a.textContent || a.innerText;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
            li[i].style.display = "";
            hasVisibleItems = true;
        } else {
            li[i].style.display = "none";
        }
    }
    dropdown.style.display = hasVisibleItems ? "block" : "none";
}

function refreshPage() {
    window.location.reload();  // Refresh the page
}

function loading(){
    $("#loading").show();
    $("#content").hide();
}

let debounceTimeout;

async function getSearchSuggestions(inputElement, suggestionsBoxElement) {
    const input = inputElement.value;
    if (!input) {
        suggestionsBoxElement.style.display = 'none';
        return;
    }
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/get_search_results/${encodeURIComponent(input)}`);
            const suggestions = await response.json();

            if (!inputElement.value) {
                suggestionsBoxElement.style.display = 'none';
                return;
            }

            if (suggestions.length > 0) {
                suggestionsBoxElement.innerHTML = '';
                suggestions.forEach(player => {
                    const suggestionItem = document.createElement('div');
                    suggestionItem.className = 'dropdown-item';

                    const avatarUrl = player.avatar_url
                        ? `https://cdn.legiontd2.com/${player.avatar_url}`
                        : 'https://cdn.legiontd2.com/icons/DefaultAvatar.png';

                    suggestionItem.innerHTML = `
                        <a style="text-decoration: none; color: white" href="/profile/${player.player_name}">
                        <img width="40" height="40" src="${avatarUrl}" alt="${player.player_name}'s avatar">
                        <span>${player.player_name}</span></a>
                    `;

                    suggestionItem.onclick = () => {
                        inputElement.value = player.player_name;
                        redirectToProfile();
                    };
                    suggestionsBoxElement.appendChild(suggestionItem);
                });
                suggestionsBoxElement.style.display = 'block';
            } else {
                suggestionsBoxElement.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching search suggestions:', error);
        }
    }, 200);
}


function handleEnterPress(event) {
    if (event.key === 'Enter') {
        redirectToProfile(event.target);
    }
}

function redirectToProfile(inputElement) {
    const input = inputElement.value;
    if (input) {
        window.location.href = `/profile/${encodeURIComponent(input)}`;
    }
}

document.querySelectorAll('.profile-input').forEach(input => {
    input.addEventListener('keydown', handleEnterPress);
});


function redirectToGame() {
    const input = document.getElementById('gameInput').value;
    if(input) {
        window.location.href = `/gameviewer/${input}`;
    }
}