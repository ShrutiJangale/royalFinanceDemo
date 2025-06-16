from django.urls import path
from . import views

app_name = 'statement_analyzer' # Optional: for namespacing URLs

urlpatterns = [
    path('upload/', views.upload_and_analyze_statement, name='upload_statement'),
    path('transactions/', views.view_transactions_data, name='view_transactions_data'),
    path('revalidate/', views.revalidate_transactions, name='revalidate_transactions'),
    path('issues/', views.view_other_issue, name='view_other_issue')
]