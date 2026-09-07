// pages/login.js — login page controller.

import { login, getSession } from '../auth.js';

// If already logged in, skip straight to the app
if (getSession()) {
  window.location.href = '/assistente';
}

const form    = document.getElementById('login-form');
const emailEl = document.getElementById('email');
const passEl  = document.getElementById('password');
const errorEl = document.getElementById('login-error');
const submit  = document.getElementById('login-submit');

const ERRORS = {
  invalid_credentials: 'E-mail ou senha inválidos.',
  user_not_found:      'Usuário não encontrado.',
  cognito_error:       'Erro de autenticação no Cognito — tente novamente.',
};

function showError(code) {
  errorEl.textContent = ERRORS[code] || `Erro: ${code}`;
  errorEl.style.display = 'block';
}

function clearError() {
  errorEl.textContent = '';
  errorEl.style.display = 'none';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError();

  const email    = emailEl.value.trim();
  const password = passEl.value;
  if (!email || !password) { showError('invalid_credentials'); return; }

  submit.disabled  = true;
  submit.textContent = 'Autenticando…';
  try {
    await login(email, password);
    window.location.href = '/assistente';
  } catch (err) {
    showError(err.message);
  } finally {
    submit.disabled = false;
    submit.textContent = 'Entrar';
  }
});
