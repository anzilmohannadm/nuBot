let selectedUserId = null;
let selectedPlanName = null;

document.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem("x-access-token");

  // Load the modal HTML
  fetch('/api/nubot/amadeus-air-ruler/update_subscription', {
    method: 'GET',
    headers: { 'x-access-token': token },
  })
    .then(response => response.text())
    .then(html => {
      document.body.insertAdjacentHTML('beforeend', html);
    })
    .catch(console.error);

  // Click delegation
  document.body.addEventListener('click', e => {
    // Open plan modal
    if (e.target.matches('.choose-plan-btn')) {
      selectedUserId = parseInt(e.target.getAttribute('data-user-id'));
      document.getElementById('choosePlanModal').classList.remove('hidden');
    }

    // Close plan modal
    if (e.target.matches('.close-btn') || e.target.id === 'choosePlanModal') {
      document.getElementById('choosePlanModal').classList.add('hidden');
      selectedUserId = null;
    }

    // Plan "Activate" button clicked
    if (e.target.matches('.pricing-card .btn')) {
      selectedPlanName = e.target.closest('.pricing-card').querySelector('.plan-title').textContent.trim();

      if (!selectedUserId) {
        console.error("No user ID selected!");
        return;
      }

      // Show confirmation modal
      document.getElementById("confirmationModal").style.display = "flex";
    }

    // Confirm Yes
    if (e.target.id === 'confirmBtn') {
      confirmSubscriptionUpdate(token);
    }

    // Confirm No
    if (e.target.id === 'cancelBtn') {
      closeConfirmationModal();
    }
  });
});

// ✅ Submit confirmed subscription change
function confirmSubscriptionUpdate(token) {
  const payload = {
    intUserId: selectedUserId,
    strSubName: selectedPlanName
  };

  fetch('/api/nubot/amadeus-air-ruler/update_subscription', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-access-token': token
    },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('choosePlanModal').classList.add('hidden');
    closeConfirmationModal();
    selectedUserId = null;
    selectedPlanName = null;

    fetchUserSubscriptionDetails().then(() => {
      showModal("User subscription updated successfully ✅");
    });
  })
  .catch(err => {
    console.error("Error updating plan:", err);
    closeConfirmationModal();
    showModal("Failed to update plan.");
  });
}

function closeConfirmationModal() {
  document.getElementById("confirmationModal").style.display = "none";
}

function showModal(message) {
  document.getElementById("modalMessage").textContent = message;
  document.getElementById("messageModal").style.display = "flex";
}

function closeModal() {
  document.getElementById("messageModal").style.display = "none";
}
