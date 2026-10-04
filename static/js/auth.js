/**
 * Authentication Form Validations
 */
document.addEventListener("DOMContentLoaded", () => {
  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", (e) => {
      const pwd = document.getElementById("password").value;
      const confirmPwd = document.getElementById("confirm_password").value;

      if (pwd.length < 8) {
        e.preventDefault();
        showToast("Password must be at least 8 characters long.", "danger");
        return;
      }
      if (!/\d/.test(pwd)) {
        e.preventDefault();
        showToast("Password must contain at least one number.", "danger");
        return;
      }
      if (pwd !== confirmPwd) {
        e.preventDefault();
        showToast("Passwords do not match.", "danger");
        return;
      }
    });
  }
});
