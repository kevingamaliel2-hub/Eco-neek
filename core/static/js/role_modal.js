// Modal de selección de rol para Google Signup
let googleUserData = null;

function openRoleModal(userData) {
  googleUserData = userData;
  document.getElementById('roleModal').style.display = 'flex';
}

function closeRoleModal() {
  document.getElementById('roleModal').style.display = 'none';
  googleUserData = null;
}

async function selectRole(role) {
  if (!googleUserData) return;
  closeRoleModal();
  // Mostrar loading
  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'loading-overlay';
  loadingDiv.innerHTML = '<div class="spinner"></div><p>Procesando...</p>';
  document.body.appendChild(loadingDiv);
  try {
    const response = await fetch('/google-register-callback/', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify({
        email: googleUserData.email,
        name: googleUserData.name,
        role: role
      })
    });
    const data = await response.json();
    if (data.success) {
      window.location.href = data.redirect;
    } else {
      alert('Error: ' + data.message);
    }
  } catch (error) {
    console.error('Error:', error);
    alert('Error al procesar la solicitud');
  } finally {
    document.body.removeChild(loadingDiv);
  }
}

document.addEventListener('DOMContentLoaded', function() {
  const googleButtons = document.querySelectorAll('a[href*="google"]');
  googleButtons.forEach(btn => {
    btn.addEventListener('click', async function(e) {
      e.preventDefault();
      try {
        // Aquí usarías la API de Google para obtener los datos
        // Por ahora, simulamos con un prompt
        const email = prompt('Ingresa tu correo de Google (demo):', 'usuario@gmail.com');
        const name = prompt('Ingresa tu nombre (demo):', 'Usuario Demo');
        if (email && name) {
          openRoleModal({ email, name });
        }
      } catch (error) {
        console.error('Error:', error);
      }
    });
  });
});
