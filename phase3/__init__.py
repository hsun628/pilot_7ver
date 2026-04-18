# models

from otree.api import *
from settings import DEBUG
from settings import num_participant

class C(BaseConstants):
    NAME_IN_URL = 'phase3'
    PLAYERS_PER_GROUP = 2 if DEBUG else int(num_participant)
    NUM_ROUNDS = 3 if DEBUG else 10
    Winner_Reward = 100
    reasoning_rounds = [1, 3] if DEBUG else [1, 5, 10]

class Subsession(BaseSubsession):
    def creating_session(self):
        if self.round_number == 1:
            self.group_like_round("phase_1", 1)

import random

class Group(BaseGroup):
    mean_number = models.FloatField()
    target_number = models.FloatField()

def set_payoffs(subsession: Subsession): # because we use wait_for_all_groups
    for group in subsession.get_groups():
        all_decisions = [p.decision for p in group.get_players()]
        
        group.mean_number = sum(all_decisions) / C.PLAYERS_PER_GROUP
        group.target_number = 1.3 * group.mean_number

        for p in group.get_players():
            p.distance = abs(p.decision - group.target_number)
            p.payoff = cu(0)

        all_distances = [p.distance for p in group.get_players()]
        min_dist = min(all_distances)
        winners = [p for p in group.get_players() if p.distance == min_dist]
        lucky_winner = random.choice(winners)

        for p in group.get_players():
            if p == lucky_winner:
                p.is_luckywinner_2 = True   
                p.payoff = cu(C.Winner_Reward)
            else:
                p.is_luckywinner_2 = False 
                p.payoff = cu(0)

            p.participant.vars[f'reason_2_{p.round_number}'] = p.reason if p.round_number in C.reasoning_rounds else None
            p.participant.vars[f'decision_2_{p.round_number}'] = p.decision
            p.participant.vars[f'payoff_2_{p.round_number}'] = p.payoff
            p.participant.vars[f'is_luckywinner_2_{p.round_number}'] = p.is_luckywinner_2

class Player(BasePlayer):
    distance = models.FloatField()
    decision = models.IntegerField(
        min = 100,
        max = 200,
        label = "請選擇您的決策數字：",
    )
    reason = models.LongStringField(
        label = "請說明您選擇該數字的理由：",
        initial = ""
    )
    is_luckywinner_2 = models.BooleanField(
        initial = False
    )

##############################################################################

# pages

from otree.api import *

class InstructionPage(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1
    
    def vars_for_template(player):
        num_player_per_group = C.PLAYERS_PER_GROUP
        return {
            "group_size": int(num_player_per_group)
        }

class Phase3StartWaitPage(WaitPage):
    title_text = "請等待其他受試者完成準備"

    wait_for_all_groups = True

    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class p_beauty(Page):
    form_model = 'player'
    form_fields = ['decision']

class reasoning_roundsWaitPage(WaitPage):
    title_text = "請等待所有受試者完成決策"
    
    wait_for_all_groups = True # wait for all groups before revealing reasoning rounds

    @staticmethod
    def is_displayed(player):
        return player.round_number in C.reasoning_rounds


class reasoning(Page):
    form_model = 'player'
    form_fields = ['reason']

    @staticmethod
    def is_displayed(player):
        return player.round_number in C.reasoning_rounds
    
    # block forbidden inputs
    @staticmethod
    def error_message(player, values):
        content = values['reason'].strip() # .strip removes leading/trailing blankspace

        if len(content) == 0: # block empty input
            return "理由欄位不能為空，請輸入您的決策思考過程。"

        if len(set(content)) < 3 and len(content) > 0: # block too short, single-word, or repetitive inputs
            return "請勿輸入過短、單一，或重複的文字內容。"
        

class DecisionWaitPage(WaitPage):
    title_text = "請等待所有受試者完成決策"

    wait_for_all_groups = True
    after_all_players_arrive = 'set_payoffs'

class Results(Page):
    @staticmethod
    def vars_for_template(player):
        group_history = player.group.in_all_rounds()
        history_data = []

        for g in group_history:
            history_data.append({
                'round': g.round_number,
                'decision': f"{player.in_round(g.round_number).decision}",
                'mean': f"{g.mean_number:.2f}",
                "target": f"{g.target_number:.2f}",
                "reason": player.in_round(g.round_number).reason if g.round_number in C.reasoning_rounds else None,
                'is_current': g.round_number == player.round_number,
                'is_luckywinner_2': player.in_round(g.round_number).is_luckywinner_2
            })

        if player.round_number == C.NUM_ROUNDS:
            round_payoffs = {r: player.in_round(r).payoff for r in range(1, C.NUM_ROUNDS + 1)}
            sum_payoffs = sum(round_payoffs.values())
            player.participant.vars["phase3_round_payoffs"] = round_payoffs
            player.participant.vars["phase3_sum_payoffs"] = sum_payoffs
            
        return {
            'history_data': history_data
        }
    

class ResultsWaitPage(WaitPage):
    title_text = "請等待所有受試者確認結果"

    wait_for_all_groups = True

page_sequence = [
    InstructionPage, 
    Phase3StartWaitPage,
    p_beauty, 
    reasoning_roundsWaitPage,
    reasoning,
    DecisionWaitPage,
    Results,
    ResultsWaitPage
]
