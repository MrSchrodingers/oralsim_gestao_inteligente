import io

from docx import Document
from docx.text.paragraph import Paragraph


class CordialLetterService:
    """
    Serviço para gerar uma carta em formato .docx a partir de um template,
    preenchendo placeholders com dados de um contexto.
    """

    def __init__(self, template_path: str):
        self.template_path = template_path

    def _replace_text_in_paragraph(self, paragraph: Paragraph, context: dict):
        """
        Substitui placeholders num parágrafo de forma segura, usando apenas a API pública.
        """
        if '{' not in paragraph.text:
            return

        # Constrói o texto completo do parágrafo a partir de todos os seus 'runs'
        full_text = "".join(run.text for run in paragraph.runs)
        
        # Faz todas as substituições necessárias na variável de texto
        for key, value in context.items():
            full_text = full_text.replace(f"{{{key}}}", str(value))
        
        # Coloca o texto final no primeiro 'run'
        # e limpa os restantes 'runs' do parágrafo.
        if paragraph.runs:
            # Mantém a formatação original do primeiro 'run'
            original_run = paragraph.runs[0]
            original_run.text = full_text # Coloca o texto completo aqui
            
            # Limpa o texto de todos os outros 'runs'
            for i in range(1, len(paragraph.runs)):
                paragraph.runs[i].text = ""

    def generate_letter(self, context: dict) -> io.BytesIO:
        """
        Carrega o template e substitui os placeholders em todas as partes do documento.
        """
        document = Document(self.template_path)

        # Itera sobre os parágrafos do corpo principal
        for p in document.paragraphs:
            self._replace_text_in_paragraph(p, context)

        # Itera sobre as tabelas
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        self._replace_text_in_paragraph(p, context)
        
        # Itera sobre cabeçalhos e rodapés
        for section in document.sections:
            if section.header:
                for p in section.header.paragraphs:
                    self._replace_text_in_paragraph(p, context)
            if section.footer:
                for p in section.footer.paragraphs:
                    self._replace_text_in_paragraph(p, context)

        # Salva o documento modificado
        file_stream = io.BytesIO()
        document.save(file_stream)
        file_stream.seek(0)
        return file_stream