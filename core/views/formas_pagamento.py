from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

from core.services.criar_usuario import criar_usuario_com_ecosistema


class FormasPagamentoView(View):
    template_name = "formas_pagamento.html"

    def get(self, request):
        # Apenas exibe a landing page
        return render(request, self.template_name)
