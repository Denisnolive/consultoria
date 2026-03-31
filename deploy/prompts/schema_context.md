# Catalogo de tabelas liberadas

A tabela liberada é a parametros, onde estão dispostas informações que devem ser consultadas conforme a orientação passada pelo usuário.


## Exemplo de estrutura

### PARAMETROS

- Nome da Tabela: paramentrtos
- Finalidade: dados de parametros de funções.
- Colunas uteis:
  - ds_funcao
  - nr_sequencia
  - ds_parametro


## Regras adicionais

- Use o modelo de select abaixo para otimizar as pesquisas solicitadas.
- Perguntas como "e possivel modificar", "ha parametro para", "onde habilita", "como bloquear", "como permitir" e similares devem ser interpretadas como busca de parametros relacionados ao assunto informado pelo usuario.
- Nesses casos, extraia as palavras-chave de negocio da pergunta e pesquise em ds_parametro com LIKE, em vez de responder sobre escrita no banco.
- Exemplo: para "E possivel modificar o volume de solucoes?", pesquisar por termos como volume, solucoes, modificar, permitir e infundir na tabela PARAMETROS.
select distinct
ds_funcao,
nr_sequencia, 
ds_parametro
from PARAMETROS
where upper(ds_parametro) like upper('%USE PARA INCLUIR PALAVRAS APRESENTADAS PELO USUÁRIO%')
order by 1
