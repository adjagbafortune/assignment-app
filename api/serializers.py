from rest_framework import serializers
from users.models import User
from .models import Assignment, Question, Choice, GradedAssignment


class StringSerializer(serializers.StringRelatedField):
    def to_internal_value(self, value):
        return value


class QuestionSerializer(serializers.ModelSerializer):
    choices = StringSerializer(many=True)

    class Meta:
        model = Question
        fields = ('id', 'choices', 'question', 'order')


class AssignmentSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    teacher = StringSerializer(many=False)

    class Meta:
        model = Assignment
        fields = ('__all__')

    def get_questions(self, obj):
        questions = QuestionSerializer(obj.questions.all(), many=True).data
        return questions

    def create(self, request):
        data = request.data

        # 1. Création de l'Assignment
        assignment = Assignment()
        teacher = User.objects.get(username=data['teacher'])
        assignment.teacher = teacher
        assignment.title = data['title']
        assignment.save()

        # 2. Création des questions et de leurs choix respectifs
        for order, q in enumerate(data['questions'], start=1):
            newQ = Question()
            newQ.question = q['title']
            newQ.order = order
            newQ.assignment = assignment
            newQ.save()  # On sauvegarde la question pour pouvoir lui ajouter des choix (relation ManyToMany)

            correct_choice = None
            for c in q['choices']:
                newC = Choice()
                newC.title = c
                newC.save()
                newQ.choices.add(newC)
                
                # On mémorise le choix qui correspond à la bonne réponse transmise par le frontend
                if c == q['answer']:
                    correct_choice = newC

            # Si la bonne réponse correspond bien à un des choix créés, on l'assigne
            if correct_choice:
                newQ.answer = correct_choice
                newQ.save()
                
        return assignment


class GradedAssignmentSerializer(serializers.ModelSerializer):
    student = StringSerializer(many=False)

    class Meta:
        model = GradedAssignment
        fields = ('__all__')

    def create(self, request):
        data = request.data

        assignment = Assignment.objects.get(id=data['asntId'])
        student = User.objects.get(username=data['username'])

        graded_asnt = GradedAssignment()
        graded_asnt.assignment = assignment
        graded_asnt.student = student

        # Tri des questions par leur champ 'order' pour correspondre aux clés du frontend
        questions = assignment.questions.all().order_by('order')
        user_answers = data.get('answers', {})

        answered_correct_count = 0
        
        # Parcours sécurisé des questions basées sur leur position (1-based index comme React)
        for i, question in enumerate(questions):
            # Récupération sécurisée : si la clé '1', '2' n'existe pas, retourne None au lieu de crasher
            student_answer = user_answers.get(str(i + 1))
            
            if question.answer and question.answer.title == student_answer:
                answered_correct_count += 1

        # Calcul de la note avec protection contre la division par zéro
        total_questions = len(questions)
        grade = (answered_correct_count / total_questions * 100) if total_questions > 0 else 0
        
        graded_asnt.grade = grade
        graded_asnt.save()
        return graded_asnt