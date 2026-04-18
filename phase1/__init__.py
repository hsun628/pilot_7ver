# models

from otree.api import *
from settings import DEBUG
from settings import num_participant

class C(BaseConstants):
    NAME_IN_URL = 'phase1'
    PLAYERS_PER_GROUP = 2 if DEBUG else int(num_participant)
    NUM_ROUNDS = 1 if DEBUG else 3
    Correct_Prediction = ["A", "B", "Tie"] # predefined correct predictions (may be randomized)
    Prediction_Reward = cu(50)

    midterm_examples = {
            1: "明天有期中考，而我目前還有兩個章節沒讀。如果現在睡覺，明天早上很可能來不及複習。雖然熬夜很累，但至少能把重點看完，所以我決定先讀完再睡。",
            2: "明天有期中考，而我目前還有兩個章節沒讀。雖然熬夜會很累，但我還是想先把內容看一看，至少把一些重點翻過一遍，所以我決定先讀完再睡。",
            3: "明天有期中考，而我目前還有兩個章節沒讀。如果現在睡覺，可能會比較舒服，也比較不會那麼累，但明天早上很可能來不及複習，所以我決定先讀完再睡。",
            4: "明天有期中考，我覺得現在還需要再準備一下，如果現在這樣去考試可能會導致我考試的時候都不會寫。雖然熬夜很累，但至少能把重點看完，所以我決定先讀完再睡。",
            5: "明天有期中考，而我目前其實還有兩個章節還沒有讀完，也就是說還有一部分內容還沒有準備好。如果我現在就直接去睡覺的話，等到明天早上再起來準備，很可能就沒有足夠的時間把這些還沒讀完的部分重新複習一遍，因此很可能會來不及好好看過重點。雖然熬夜讀書確實會讓人覺得很累，但如果現在先把書讀完，至少還能把重要的重點內容先看過一次。這樣一來，對於明天的考試至少會比較有準備一些。我最後還是決定先把剩下的部分讀完，再去休息睡覺。",
            6: "我剛看窗外的天色整片變得很暗、雲層厚到不行，而且我看氣象預報也說今天降雨機率有80%。我猜等一下出門一定會下大雨，怕被淋得濕答答的，所以決定還是帶一下傘比較保險。",
            7: "我剛看窗外的天色整片變得很暗、雲層厚到不行。我猜等一下出門一定會下大雨，怕被淋得濕答答的，所以決定還是帶一下傘比較保險。"
        }

    round_reasonings = {
            1: (midterm_examples.get(1), midterm_examples.get(2)),
            2: (midterm_examples.get(4), midterm_examples.get(1)),
            3: (midterm_examples.get(1), midterm_examples.get(5))
        }

    gpt_feedback = {
        1: "理由A較具體，因為它不只提到還有兩章沒讀，還明確說出如果現在睡，明早可能來不及複習；理由B則用了較模糊的說法，推理鏈較弱。", # 1 vs 2
        2: "理由B較具體，因為它提供了明確資訊（還有兩章沒讀）與清楚推論（現在睡會來不及複習）；理由A較偏主觀感受，具體性較弱。", # 4 vs 1
        3: "理由B只是把理由A的相同資訊與推理過程用更長的方式重述，沒有新增新的資訊或推論，因此具體程度相近。", # 1 vs 5
        4: "理由A較具體，因為它不只說明先睡會來不及複習，還清楚交代熬夜的代價與收益；理由B雖補充先睡較舒服，但這個資訊較不具策略性。" # 1 vs 3
    }

class Subsession(BaseSubsession):
    pass             

class Group(BaseGroup):
    pass

def calculate_results(self):
    correct_answer = C.Correct_Prediction[self.round_number - 1]

    for p in self.get_players():
        p.is_correct = (p.prediction == correct_answer)
        p.payoff = C.Prediction_Reward if p.is_correct else cu(0)
    
class Player(BasePlayer):  
    prediction = models.StringField(
        choices = ["A", "Tie", "B"],
    )
    is_correct = models.BooleanField()


#############################################################################

# pages

from otree.api import *

class welcome(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1
    
class Phase1StartWaitPage(WaitPage):
    title_text = "請等待其他受試者完成準備"

    wait_for_all_groups = True

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class Prediction(Page):
    form_model = 'player'
    form_fields = ['prediction']

    @staticmethod
    def vars_for_template(player):
        reason_a, reason_b = C.round_reasonings.get(player.round_number)

        return {
            "reason_a": reason_a,
            "reason_b": reason_b
        }

class PredictionWaitPage(WaitPage):
    title_text = "請等待其他受試者完成預測"
    
    after_all_players_arrive = 'calculate_results'

class Results(Page):
    @staticmethod
    def vars_for_template(player):
        reason_a, reason_b = C.round_reasonings.get(player.round_number)
        result_text = "正確" if player.is_correct else "錯誤"
        feedback = C.gpt_feedback.get(player.round_number)

        correct_answer = C.Correct_Prediction[player.round_number - 1]
        if correct_answer == "A":
            answer_text = "理由A"
        elif correct_answer == "B":
            answer_text = "理由B"
        elif correct_answer == "Tie":
            answer_text = "兩者平手"

        return {
            "reason_a": reason_a,
            "reason_b": reason_b,
            "result_text": result_text,
            "answer_text": answer_text,
            "feedback": feedback
        }

class ResultsWaitPage(WaitPage):
    title_text = "請等待其他受試者確認結果"

page_sequence = [
    welcome,
    Phase1StartWaitPage,
    Prediction,
    PredictionWaitPage,
    Results,
    ResultsWaitPage
]
