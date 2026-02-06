from django.db import models

# Create your models here.

class Projeto(models.Model):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    capa = models.ImageField(upload_to='projetos/capas/', default='projetos/capas/default.png')
    url = models.URLField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo
    
    @classmethod
    def criar_projeto(cls, titulo, descricao, capa, url=None):
        projeto = cls(titulo=titulo, descricao=descricao, capa=capa, url=url)
        projeto.save()
        return projeto
    
    def atualizar_projeto(self, titulo=None, descricao=None, capa=None, url=None):
        if titulo:
            self.titulo = titulo
        if descricao:
            self.descricao = descricao
        if capa:
            self.capa = capa
        if url is not None:
            self.url = url
        self.save()
        return self

    def deletar_projeto(self):
        self.delete()
    