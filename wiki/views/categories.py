from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from ..models import Category
from ..forms import CategoryForm

class CategoryListView(ListView):
    model = Category
    template_name = 'wiki/category_list.html'
    context_object_name = 'categories'

class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'wiki/category_form.html'
    permission_required = 'wiki.add_category'
    success_url = reverse_lazy('wiki:category-list')

class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'wiki/category_form.html'
    permission_required = 'wiki.change_category'
    success_url = reverse_lazy('wiki:category-list')

class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Category
    template_name = 'wiki/category_confirm_delete.html'
    permission_required = 'wiki.delete_category'
    success_url = reverse_lazy('wiki:category-list')
