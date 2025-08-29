document.addEventListener('DOMContentLoaded', () => {
    const queryForm = document.getElementById('queryForm');
    const confirmModal = document.getElementById('confirmModal');
    const confirmYes = document.getElementById('confirmYes');
    const confirmNo = document.getElementById('confirmNo');
    const clearButton = document.getElementById('clearButton');

    // Show custom modal on form submission
    queryForm.addEventListener('submit', function (event) {
        event.preventDefault(); // Prevent form submission
        confirmModal.style.display = 'flex'; // Show the modal
    });

    // Handle "Yes" button
    confirmYes.addEventListener('click', () => {
        confirmModal.style.display = 'none'; // Hide the modal
        queryForm.submit(); // Submit the form
    });

    
    // Handle "No" button
    confirmNo.addEventListener('click', () => {
        confirmModal.style.display = 'none'; // Hide the modal
    });

    // Handle "Clear" button
    clearButton.addEventListener('click', () => {
        const queryElemet = document.getElementById('query')
        queryElemet.textContent = '';
        console.log(queryElemet);  // Log to check form reset
    });
});
