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
            if (header.innerText.startsWith("Tier") && header.parentNode.rowIndex === 1) {
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

function myFunction() {
    document.getElementById("myDropdown").classList.toggle("show");
}

function filterFunction() {
  const input = document.getElementById("myInput");
  const filter = input.value.toUpperCase();
  const div = document.getElementById("myDropdown");
  const ul = div.getElementsByTagName("ul")[0];
  const a = ul.getElementsByTagName("a");

  // Check if the custom input element already exists
  let firstResult = ul.getElementsByClassName('user-input-result')[0];

  if (!firstResult) {
    // If it doesn't exist, create a new list item for the user's input
    firstResult = document.createElement('li');
    firstResult.className = 'user-input-result';
    firstResult.innerHTML = `<a class="dropdown-item" href="/load/${input.value}"><img loading="lazy" style="width: 24px;" src="https://cdn.legiontd2.com/icons/DefaultAvatar.png">${input.value} - Player Search</a>`;
    ul.insertBefore(firstResult, ul.firstChild); // Insert at the top
  } else {
    // Update the custom search item with the new input
    firstResult.innerHTML = `<a class="dropdown-item" href="/load/${input.value}"><img loading="lazy" style="width: 24px;" src="https://cdn.legiontd2.com/icons/DefaultAvatar.png">${input.value} - Player Search</a>`;
  }

  // Show the first custom search result if the user has entered something
  if (input.value.trim() !== "") {
    firstResult.style.display = "";
  } else {
    firstResult.style.display = "none";
  }

  // Loop through the existing list items and filter based on input
  for (let i = 1; i < ul.children.length; i++) {
    const item = ul.children[i].getElementsByTagName("a")[0];
    const txtValue = item.textContent || item.innerText;
    if (txtValue.toUpperCase().indexOf(filter) > -1) {
      ul.children[i].style.display = "";
    } else {
      ul.children[i].style.display = "none";
    }
  }

  // Add event listener for Enter key
  input.addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
      event.preventDefault(); // Prevent form submission if inside a form

      // Find the first visible <a> element
      const firstVisibleLink = ul.querySelector('li:not([style*="display: none"]) a');

      // If found, navigate to its href
      if (firstVisibleLink) {

        // Navigate to the href
        window.location.href = firstVisibleLink.href;
      }
    }
  });

  // Add event listeners to each dropdown link
  for (let i = 0; i < a.length; i++) {
    a[i].addEventListener('click', function(event) {
    });
  }
}

function filterFunction2() {
  const input = document.getElementById("myInput");
  const filter = input.value.toUpperCase();
  const dropdown = document.getElementById("myDropdown");
  const ul = dropdown.getElementsByTagName("ul")[0];
  const li = ul.getElementsByTagName("li");

  // Loop through all list items and hide those that don't match the search query
  for (let i = 0; i < li.length; i++) {
    const a = li[i].getElementsByTagName("a")[0];
    const txtValue = a.textContent || a.innerText;
    if (txtValue.toUpperCase().indexOf(filter) > -1) {
      li[i].style.display = "";
    } else {
      li[i].style.display = "none";
    }
  }
}

function refreshPage() {
    window.location.reload();  // Refresh the page
}

function loading(){
    $("#loading").show();
    $("#content").hide();
}

function redirectToProfile() {
    const input = document.getElementById('profileInput').value;
    if(input) {
        window.location.href = `/profile/${input}`;
    }
}

function redirectToGame() {
    const input = document.getElementById('gameInput').value;
    if(input) {
        window.location.href = `/gameviewer/${input}`;
    }
}

function redirectToRecap() {
    const input = document.getElementById('recapInput').value;
    if(input) {
        window.location.href = `/recap/${input}`;
    }
}

jQuery(document).ready(function($) {
    $(".player-row").click(function(event) {
        // Check if the click was done using the middle mouse button or with a modifier key (Ctrl or Command)
        if (event.which === 2 || event.metaKey || event.ctrlKey) {
            // If middle mouse button or modifier key is pressed, open in a new tab
            window.open($(this).data("href"), '_blank');
        } else {
            // Otherwise, proceed with the default behavior (redirect in the same tab)
            window.location = $(this).data("href");
        }
    });
});