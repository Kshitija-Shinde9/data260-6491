// This is the JavaScript for my grocery recall notices page.
// It is my HW1 file extended, because now the data is sent to the server instead of only being printed.

const API_URL = '/api/recalls';

// A short way to find something on the page by its id.
const el = (id) => document.getElementById(id);

// The last list the server sent me, saved so the buttons can use it.
let currentRecalls = [];


// Counts how many times I have submitted the form, and nothing else can change this count.
const submissionCounter = (() => {
    let count = 0;
    return () => {
        count = count + 1;
        return count;
    };
})();

// Checks the description and the checkbox, and gives back the problem or nothing if it is fine.
const validateForm = (descriptionValue, isChecked) => {
    const trimmedDescription = descriptionValue.trim();

    if (trimmedDescription.length <= 25) {
        return "Please write a bit more in the recall reason, it needs to be more than 25 characters.";
    }

    if (!isChecked) {
        return "You need to check the box agreeing to the terms and conditions before submitting.";
    }

    return null;
};


// Shows the page I clicked on and hides the other ones.
function showView(viewName) {
    document.querySelectorAll('.view').forEach(section => {
        section.hidden = section.id !== `view-${viewName}`;
    });

    document.querySelectorAll('.tab').forEach(tab => {
        const isActive = tab.dataset.view === viewName;
        tab.classList.toggle('is-active', isActive);
        if (isActive) {
            tab.setAttribute('aria-current', 'page');
        } else {
            tab.removeAttribute('aria-current');
        }
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => showView(tab.dataset.view));
});


let toastTimer = null;

// Shows a short message at the bottom of the page.
function showToast(message, ok = true) {
    const toast = el('toast');
    toast.textContent = message;
    toast.className = 'toast ' + (ok ? 'ok' : 'bad');
    toast.hidden = false;

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
}


// Shows only one thing at a time: loading, empty, error, or the list.
function showListState(state) {
    el('loadingState').hidden = state !== 'loading';
    el('emptyState').hidden = state !== 'empty';
    el('errorState').hidden = state !== 'error';
    el('tableWrap').hidden = state !== 'table';
}


// Asks the server for the notices, and sends the search word if there is one.
async function loadRecalls(searchTerm = '') {
    showListState('loading');

    try {
        const url = searchTerm
            ? `${API_URL}?search=${encodeURIComponent(searchTerm)}`
            : API_URL;

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`the server responded with ${response.status}`);
        }

        const recalls = await response.json();
        currentRecalls = recalls;

        displayRecalls(recalls, searchTerm);
        updateManagePanels();
    } catch (error) {
        console.error('Error loading recall notices:', error);

        el('errorText').textContent =
            `Could not reach the server on port 8191. Check that main.py is still running. (${error.message})`;
        showListState('error');

        el('navCount').textContent = '!';
    }
}


// Puts the notices into the table, or shows the empty message if there are none.
function displayRecalls(recalls, searchTerm = '') {
    const tbody = el('recallTableBody');
    tbody.innerHTML = '';

    el('navCount').textContent = recalls.length;

    // A small line saying how many results the search found.
    const note = el('searchNote');
    if (searchTerm) {
        note.textContent = `Showing ${recalls.length} result${recalls.length === 1 ? '' : 's'} for "${searchTerm}".`;
        note.hidden = false;
    } else {
        note.hidden = true;
    }

    // A different message depending on whether I searched or the list is really empty.
    if (recalls.length === 0) {
        if (searchTerm) {
            el('emptyTitle').textContent = 'No matching notices';
            el('emptyText').textContent =
                `Nothing matches "${searchTerm}". Try a different product name or supplier, or press Show All.`;
        } else {
            el('emptyTitle').textContent = 'No recall notices yet';
            el('emptyText').textContent =
                'Nothing has been reported. Use the Add Notice tab to report the first one.';
        }
        showListState('empty');
        return;
    }

    recalls.forEach(recall => {
        const row = document.createElement('tr');

        row.appendChild(makeCell('ID', recall.id, 'id-cell'));
        row.appendChild(makeCell('Product', recall.product_name, 'product-cell'));
        row.appendChild(makeCell('Supplier', recall.supplier));

        // The reason is shown as a small coloured label.
        const typeCell = document.createElement('td');
        typeCell.dataset.label = 'Reason';
        if (recall.recall_type) {
            const chip = document.createElement('span');
            chip.className = 'chip ' + chipClass(recall.recall_type);
            chip.textContent = recall.recall_type;
            typeCell.appendChild(chip);
        } else {
            typeCell.textContent = '-';
        }
        row.appendChild(typeCell);

        const actionCell = document.createElement('td');
        actionCell.className = 'actions-cell';

        const actions = document.createElement('div');
        actions.className = 'row-actions';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'icon-btn';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => startEdit(recall.id));

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'icon-btn danger';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', () => deleteRecall(recall.id));

        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
        actionCell.appendChild(actions);
        row.appendChild(actionCell);

        tbody.appendChild(row);
    });

    showListState('table');
}


// Makes one table cell, and saves the column name so it can be shown on a phone.
function makeCell(label, value, className = '') {
    const td = document.createElement('td');
    td.dataset.label = label;
    // Using textContent so apostrophes in product names cannot break my page.
    td.textContent = value;
    if (className) {
        td.className = className;
    }
    return td;
}


// Picks the colour for the reason label.
function chipClass(recallType) {
    if (recallType.includes('Seal')) return 'chip-seal';
    if (recallType.includes('Contamination')) return 'chip-contam';
    if (recallType.includes('Allergen')) return 'chip-allergen';
    if (recallType.includes('Spoiled')) return 'chip-spoiled';
    return '';
}


// Keeps the Manage page showing the correct information.
function updateManagePanels() {
    const preview = el('highestPreview');
    if (currentRecalls.length === 0) {
        preview.textContent = 'nothing left to delete';
    } else {
        const highest = currentRecalls.reduce((a, b) => (a.id > b.id ? a : b));
        preview.textContent = `ID ${highest.id} - ${highest.product_name}`;
    }

    showUpdateTarget();
}


// Shows the name of the notice that the ID box is pointing at.
function showUpdateTarget() {
    const id = parseInt(el('updateId').value);
    const match = currentRecalls.find(recall => recall.id === id);
    el('updateTarget').textContent = match
        ? match.product_name
        : (id ? `no record with ID ${id}` : '-');
}


// Q1 - runs when I submit the form, it checks the data and then sends it to the server.
el("recallForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    // Removing extra spaces so they do not count as real typing.
    const productName = el("productName").value.trim();
    const supplierName = el("supplierName").value.trim();
    const submitterEmail = el("submitterEmail").value.trim();
    const recallDescription = el("recallDescription").value.trim();
    const recallType = el("recallType").value;
    const agreeTerms = el("agreeTerms").checked;

    // If there is a problem, stop here and do not send anything.
    const problem = validateForm(recallDescription, agreeTerms);
    if (problem) {
        showToast(problem, false);
        return;
    }

    // These names must match the ones in main.py.
    const formData = {
        product_name: productName,
        supplier: supplierName,
        email: submitterEmail,
        description: recallDescription,
        recall_type: recallType
    };

    const jsonString = JSON.stringify(formData);
    console.log("form data as JSON string:", jsonString);

    const parsedData = JSON.parse(jsonString);

    // Taking out the product name and email and giving them clearer names.
    const { product_name: reportedProduct, email: reportedEmail } = parsedData;
    console.log("product name:", reportedProduct);
    console.log("submitter email:", reportedEmail);

    // Copying everything and adding the date it was submitted.
    const updatedData = { ...parsedData, submissionDate: new Date().toString() };
    console.log("updated data with submission date:", updatedData);

    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: jsonString
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add recall notice');
        }

        const newRecall = await response.json();
        console.log('Created recall notice:', newRecall);

        const currentCount = submissionCounter();
        console.log("this form has been submitted", currentCount, "time(s) so far");

        // Emptying the form so it is ready to use again.
        el("recallForm").reset();
        el("charCount").textContent = '0';

        // Go back to the home page with the new list.
        el("searchInput").value = '';
        showView('home');
        await loadRecalls();

        showToast(`Added "${newRecall.product_name}" as record ID ${newRecall.id}.`);
    } catch (error) {
        console.error('Error adding recall notice:', error);
        showToast('Could not add the recall notice: ' + error.message, false);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Report This Recall';
    }
});


// Counts the characters as I type, because I need more than 25.
el('recallDescription').addEventListener('input', (event) => {
    el('charCount').textContent = event.target.value.trim().length;
});


// Q2 - sends the new product name and supplier for one notice, the question asks for ID 1.
async function updateRecall() {
    const idInput = el('updateId');
    const productInput = el('updateProductName');
    const supplierInput = el('updateSupplierName');

    const id = parseInt(idInput.value);
    const productName = productInput.value.trim();
    const supplierName = supplierInput.value.trim();

    if (!id) {
        showToast('Please enter the Record ID you want to update.', false);
        return;
    }

    if (!productName || !supplierName) {
        showToast('Please enter both a new product name and a new supplier / brand.', false);
        return;
    }

    try {
        const response = await fetch(`${API_URL}/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                product_name: productName,
                supplier: supplierName
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update recall notice');
        }

        const updatedRecall = await response.json();
        console.log('Updated recall notice:', updatedRecall);

        // Empty the boxes and go back to the home page with the new list.
        productInput.value = '';
        supplierInput.value = '';
        el("searchInput").value = '';
        showView('home');
        await loadRecalls();

        showToast(`Record ID ${updatedRecall.id} updated.`);
    } catch (error) {
        console.error('Error updating recall notice:', error);
        showToast('Could not update the record: ' + error.message, false);
    }
}


// The Edit button fills in the update form for me so I do not type the ID myself.
function startEdit(id) {
    const recall = currentRecalls.find(r => r.id === id);
    if (!recall) {
        return;
    }

    el('updateId').value = recall.id;
    el('updateProductName').value = recall.product_name;
    el('updateSupplierName').value = recall.supplier;

    showView('manage');
    updateManagePanels();
    el('updateProductName').focus();
}

// Keeps the line under the ID box correct while I type.
el('updateId').addEventListener('input', showUpdateTarget);


// Q3 - deletes the notice with the biggest ID number.
async function deleteHighestRecall() {
    if (currentRecalls.length === 0) {
        showToast('There are no recall notices to delete.', false);
        return;
    }

    const highest = currentRecalls.reduce((a, b) => (a.id > b.id ? a : b));

    if (!confirm(`Delete the notice with the highest ID?\n\nID ${highest.id} - ${highest.product_name}`)) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/highest`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete recall notice');
        }

        console.log('Deleted the recall notice with the highest ID');

        // Go back to the home page with the new list.
        el("searchInput").value = '';
        showView('home');
        await loadRecalls();

        showToast(`Deleted record ID ${highest.id}, the highest ID.`);
    } catch (error) {
        console.error('Error deleting recall notice:', error);
        showToast('Could not delete: ' + error.message, false);
    }
}


// Deletes one notice using the Delete button on its row.
async function deleteRecall(id) {
    const recall = currentRecalls.find(r => r.id === id);
    const name = recall ? recall.product_name : `ID ${id}`;

    if (!confirm(`Delete this recall notice?\n\nID ${id} - ${name}`)) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/${id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete recall notice');
        }

        await loadRecalls(el('searchInput').value.trim());
        showToast(`Deleted record ID ${id}.`);
    } catch (error) {
        console.error('Error deleting recall notice:', error);
        showToast('Could not delete: ' + error.message, false);
    }
}


// Q4 - searches by product name or supplier.
async function searchRecalls() {
    const searchTerm = el('searchInput').value.trim();
    await loadRecalls(searchTerm);
}

// Pressing Enter in the search box also searches.
el('searchInput').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        searchRecalls();
    }
});

// Empties the search box and shows the whole list again.
async function clearSearch() {
    el('searchInput').value = '';
    await loadRecalls();
}


// Loads the list as soon as the page opens.
document.addEventListener('DOMContentLoaded', () => {
    loadRecalls();
});
