from otree.api import *
from openai import OpenAI
import os
from dotenv import load_dotenv

import random
import json
import re
import time
import threading

from otree.database import db

from settings import DEBUG
from settings import num_participant

load_dotenv()

my_api_key = os.getenv('api_key')   # DO NOT PASTE YOUR API_KEY HERE!
model_used = "gpt-5.2"

client = OpenAI(api_key = my_api_key)  # DO NOT PASTE YOUR API_KEY HERE!

class C(BaseConstants):
    NAME_IN_URL = 'phase_AI'
    PLAYERS_PER_GROUP = 2 if DEBUG else int(num_participant)
    NUM_ROUNDS = 3 if DEBUG else 10
    Pass_Reward = 100 # the payoff for players who pass the reason assessment
    reasoning_rounds = [1, 3] if DEBUG else [1, 5, 10]

    PHASE_CONFIG = [
        {
            'experimental_rules': 
            f"""
            * Part II consists of 10 rounds. At the beginning, the computer randomly divides all participants into groups, and the number of participants in each group will be displayed on the screen.
            * In each round, you must choose an integer between 0 and 100.
            * The average of all numbers chosen by participants in your group is called the "Average Number."
            * The person whose choice is closest to **0.7 times the Average Number** (called the "Target Number") is the "Decision Winner" of the round. In the event of a tie, the computer will randomly select one winner.
            * After each round ends, the computer will display the past "Average Number" and "Target Number" for your group.""",

            'history_key': 'reason_history',
            'payoff_prefix': 'phase2',
            "payoff_var": "total_phase2_payoff",
            'var_prefix': ''
        },
        {
            'experimental_rules':
            f"""
            * Part III consists of 10 rounds. Your group members are exactly the same as in Part II. The number of participants in each group will be displayed on the screen.
            * In each round, you must choose an integer between 100 and 200.
            * The average of all numbers chosen by participants in your group is called the "Average Number."
            * The person whose choice is closest to **1.3 times the Average Number** (called the "Target Number") is the "Decision Winner" of the round. In the event of a tie, the computer will randomly select one winner.
            * After each round ends, the computer will display the "Average Number" and "Target Number" for your group.""",

            'history_key': 'reason_history_2',
            'payoff_prefix': 'phase3',
            "payoff_var": "total_phase3_payoff",
            'var_prefix': '_2'
        }
    ]

class Subsession(BaseSubsession):
    def creating_session(self):
        if self.round_number == 1:
            self.group_like_round("phase_1", 1)

class Group(BaseGroup):
    pass 


_thread_storage = {}

class Player(BasePlayer):
    gpt_reason = models.LongStringField()
    gpt_analysis = models.LongStringField() 
    winner_type = models.StringField()
    payoff_adj = models.CurrencyField()
    is_flipped = models.BooleanField()
    

    gpt_reason_2 = models.LongStringField()
    gpt_analysis_2 = models.LongStringField() 
    winner_type_2 = models.StringField()
    payoff_adj_2 = models.CurrencyField()
    is_flipped_2 = models.BooleanField()
    

    is_gpt_finished = models.BooleanField(initial = False)

    def gpt_process(self, p_vars):
        p_id = p_vars.get("id_in_subsession")
        results = {}
        db_data = {}

        if p_vars.get("reason_history"):
            _thread_storage[p_id] = {"status": "already_finished"}
            return

        for config in C.PHASE_CONFIG:
            phase_id = config["payoff_prefix"]

            history = []
            round_data = {}
            prefix = config["var_prefix"]
            phase_payoff = p_vars.get(f"{config["payoff_prefix"]}_round_payoffs", {})
            final_payoff = {r: cu(phase_payoff.get(r)) for r in range(1, C.NUM_ROUNDS + 1)}

            time.sleep((p_id - 1) * 0.5)

            for r in C.reasoning_rounds:
                human_reason = p_vars.get(f"reason{prefix}_{r}", "").strip()
                human_decision = p_vars.get(f'decision{prefix}_{r}')
                is_luckywinner = p_vars.get(f"is_luckywinner{prefix}_{r}")
                luckywinner_text = "是" if is_luckywinner else "否"

                print(f"=====當前處理回合 {r} - 受試者{p_vars.get("id_in_subsession")} =====")
                print(f"human_decision: {human_decision}")
                print(f"human_reason: '{human_reason}'")

                if human_reason and human_decision is not None:
                    try:
                        print(f"受試者{p_id} 正在呼叫API")
                    
                        target_is_flipped = random.choice([True, False])

                        gpt_reason = gpt_generate(config["experimental_rules"], r, human_decision)
                        winner_type, gpt_analysis = gpt_judge(config["experimental_rules"], human_reason, gpt_reason, target_is_flipped)

                        if winner_type in ["Human", "Tie"]:
                            final_payoff[r] = cu(C.Pass_Reward)
                            payoff_adj = cu(C.Pass_Reward) - cu(p_vars.get(f"payoff{prefix}_{r}"))
                            result_text = "您的理由較具體"
                        else:
                            final_payoff[r] = cu(0)
                            payoff_adj = - cu(p_vars.get(f"payoff{prefix}_{r}"))
                            result_text = "AI生成的理由較具體"

                        round_data[r] = {
                            "is_flipped": target_is_flipped,
                            "gpt_reason": gpt_reason,
                            "gpt_analysis": gpt_analysis,
                            "winner_type": winner_type,
                            "payoff_adj": payoff_adj
                        }

                        history.append({
                            "round": r,
                            "human_reason": human_reason,
                            "gpt_reason": gpt_reason,
                            "winner_type": winner_type,
                            "luckywinner_text": luckywinner_text,
                            "result_text": result_text,
                            "final_payoff": final_payoff[r] 
                        })

                        print(f"API呼叫成功 - winner: {winner_type}")

                    except Exception as e:
                        print(f"Round_{r} API呼叫失敗: {e}")

            total_phase_payoff = sum(final_payoff.values())

            results[config['history_key']] = history
            results[config['payoff_var']] = total_phase_payoff
            db_data[phase_id] = round_data

        _thread_storage[p_id] = {
            "status": "done",
            "data": results,
            "db": db_data
        } 


########################################################################################################################

def gpt_generate(experimental_rules ,round_number, participant_decision):

    generate_prompt = f"""

        ### Role: 
            You are a college student participating in an economics experiment. Your task is to write a reasoning for a specific decision.

        ### Task: 
            You will be presented with a participant's decision from the experiment described below. Based on that decision, write a reasoning (about 30-40 characters in Traditional Chinese, 50 characters at most) explaining the underlying thoughts and the information used for that decision. The reasoning should follow the requirements below:
            * **Requirements**:
                * Your reasoning should include the information and beliefs you observed or used, and demonstrate the process of how you derived the decision from said information and beliefs.
                * The reasoning should sound like a real participant, not like a game theory expert.
                * Do not mention Nash equilibrium, infinite iteration, dominance, or formal strategic terminologies.
                * You may think strategically, but do not fully formalize or optimize the reasoning.* Use natural, conversational language.
                * Some uncertainty is allowed (e.g., “I guess”, “maybe”, “probably”).
                * The reasoning should not look highly sophisticated or mathematically complete.
                * The reasoning should be in accordance with the provided round number.

        ### Experimental Rules:
            {experimental_rules}
            
        ### Response Format:
            Please provide the participant's decision and the reasoning (in Traditional Chinese) you have written. Your response must strictly follow this JSON format:
            {{
                "round": {round_number},
                "decision": {participant_decision},
                "reasoning": "Your reasoning (about 30 characters in Traditional Chinese) explaining the underlying thoughts and the information used for the decision."
            }}
    """

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model = model_used,
                messages = [
                    {"role": "system", "content": generate_prompt},
                    {"role": "user", "content": f"""Based on the round number: {round_number} and the provided decision: {participant_decision}, write a reasoning (about 30-40 characters in Traditional Chinese, 50 characters at most) explaining the underlying thoughts and the information used for the decision. Your response must strictly follow the specified JSON format.
                """}
                ],
                response_format = {"type" : "json_object"},
                temperature = 1,   # lower value gives more stable response (0-2)
                max_completion_tokens = 300  
            )

            generate_result = response.choices[0].message.content
            data_generate = json.loads(generate_result)

            return data_generate.get("reasoning")
    
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue

            print(f"JSON / API error: {e}")
            return "JSON / API error"
    
########################################################################################################################

def gpt_judge(experimental_rules, reasoning_1, reasoning_2, is_flipped_value):  
    if is_flipped_value:
        reasons = [reasoning_2, reasoning_1]
    else:
        reasons = [reasoning_1, reasoning_2]
    
    judge_prompt = f"""

    ### Role:
        You are a professional judge. Your task is to evaluate the explanations provided by participants regarding their decision-making process.

    ### Judging Task:
        Compare the reasons provided by the following two participants. Determine which participant more specifically explains the "underlying thoughts" and the "information used" behind their decision.

    ### Evaluation Criteria (Strictly Adhere to the Following):

    * **Information & Belief:** Does the participant mention specific information they observed? Do they state their inferences or hypotheses about the current situation? Did they elaborate on how they arrive at these inferences and hypotheses?

    * **Logic & Strategy:** Does the participant demonstrate the derivation process from the aforementioned information and beliefs to their final decision?
        * **Is the logic consistent with the experimental rules? (Crucial):** Does the claimed causal relationship in the reasoning align with the experimental rules? If the reasoning fundamentally contradicts the rules or physical facts (e.g., claiming that a certain decision can achieve "Effect A," when the rules make it impossible for that decision to ever produce such an effect), the reasoning should be considered a "Logical Break." Such a reasoning must receive a lower evaluation than one that is logically self-consistent.

    * **Level of Specificity:** Is the reason specific? (For example: prefer "Because I observed A, I expected B, and therefore adopted strategy C" over "I just picked one" or "I wanted to choose this"). You can further judge based on:
        - Whether the reason contains specific information related to the rules, rather than just a vague description.
        - Whether there are clear causal and logical relationships between sentences.

    ### Strict Prohibitions (Do NOT Consider):

    * **Do NOT judge based on the "quality" or "winning probability" of the decision:** Even if the participant's reasoning contains calculation errors or the decision itself has a very low probability of winning, as long as they clearly and logically explain their thought process, that reason should receive a higher evaluation. 

    * **Note:** Your mission is to evaluate "who more specifically explained their underlying thoughts and information used," NOT "how smart the decision was."

    * **Reasoning Length**: Do not judge the specificity or detail of a reason based on its word count. (For example: "Because I observed A, I expected B, and therefore adopted strategy C" and "Under my careful observation, I discovered A, so I expect others to do B; consequently, I decided to adopt strategy C to increase my winning probability" describe the same content. They should receive the same or very similar evaluation).

    * **Do NOT Favor "Self-Invented Jargon":** Participants may use self-invented professional-sounding terms (e.g., "Boundary Suppression Effect," "Group Deviation Law"). Do not award a higher evaluation simply because the reasoning contains these non-standard terms that appear neither in the experimental instruction nor in everyday language. 
        - Pay attention to whether the participant explicitly explains the meaning of these invented terms, or whether the terms carry concrete logical weight within their common-sense semantic context. 
        - If the reasoning becomes hollow or lacks substance once these terms are removed, the reasoning should receive a lower evaluation.

    ### Experimental instruction:
        {experimental_rules}

    ### Response Format:        
        The following are two reasonings for a decision. Please evaluate them based on the judge criterion and prohibition above.

            - reasoning_A: {reasons[0]}
            - reasoning_B: {reasons[1]}

        Please state (in the following specified JSON format) which reasoning more specifically explained the "underlying thoughts" and "information used," (If the two are extremely close, you may declare a tie) and briefly provide the reasons (in Traditional Chinese and the following specified JSON format) for your judgment.

        Your response must strictly follow this JSON format:
            {{
                "winner": "reasoning_A" or "reasoning_B" or "Tie",
                "analysis": "A brief reason for your judgement of the winner."
            }}
        
    """
    
    response = client.chat.completions.create(
        model = model_used,
        messages = [
            {"role": "system", "content": judge_prompt},
            {"role": "user", "content": f"""Please state (in the following specified JSON format) which reasoning more specifically explained the "underlying thoughts" and "information used." (If the two are extremely close, you may declare a tie). Your response must strictly follow the specified JSON format."""}],
        response_format = {"type" : "json_object"},
        temperature = 0,   # test
        max_completion_tokens = 500
    )

    judge_result = response.choices[0].message.content
    data_judge = json.loads(judge_result)
    winner = data_judge.get("winner", "")
    gpt_analysis = data_judge.get("analysis", "")


    if "reasoning_A" in winner:
        final_winner = "Human" if not is_flipped_value else "AI"
    elif "reasoning_B" in winner:
        final_winner = "AI" if not is_flipped_value else "Human"
    elif "Tie" in winner:
        final_winner = "Tie" 

    return final_winner, gpt_analysis

########################################################################################################################

# pages

class InstructionPage(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

class ProcessingPage(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1
    
    @staticmethod
    def live_method(player, data):
        if data.get("type") == "API_start":
            if not player.is_gpt_finished:
                p_vars = dict(player.participant.vars)
                p_vars["id_in_subsession"] = player.id_in_subsession

                t = threading.Thread(target = player.gpt_process, args = (p_vars, ))
                t.daemon = True
                t.start()
            return {player.id_in_group: {"status": "started"}}
        
        if data.get("type") == "check_status":
            global _thread_storage
            p_id = player.id_in_subsession
            output = _thread_storage.get(p_id)
            
            if output:
                if output.get("status") == "already_finished":
                    player.is_gpt_finished = True
                    return {player.id_in_group: {"status": "finished"}}
                
                if output.get("status") == "done":
                    data = output["data"]

                    for key, val in data.items():
                        player.participant.vars[key] = val

                    total_adj = {r: cu(0) for r in C.reasoning_rounds}

                    for config in C.PHASE_CONFIG:
                        phase_id = config["payoff_prefix"]
                        prefix = config["var_prefix"]

                        if phase_id in output["db"]:
                            phase_rounds = output["db"][phase_id]
                            
                            for r, vals in phase_rounds.items():
                                target = player.in_round(r)

                                setattr(target, f"is_flipped{prefix}", vals["is_flipped"])
                                setattr(target, f"gpt_reason{prefix}", vals["gpt_reason"])
                                setattr(target, f"gpt_analysis{prefix}", vals["gpt_analysis"])
                                setattr(target, f"winner_type{prefix}", vals["winner_type"])

                                adj_val = vals.get("payoff_adj")
                                setattr(target, f"payoff_adj{prefix}", adj_val)

                                total_adj[r] += adj_val
                        
                    for r, final_adj in total_adj.items():
                        player.in_round(r).payoff = final_adj

                    player.participant.vars["reason_history"] = data["reason_history"]
                    player.participant.vars["reason_history_2"] = data["reason_history_2"]
                    player.participant.vars["total_phase2_payoff"] = data["total_phase2_payoff"]
                    player.participant.vars["total_phase3_payoff"] = data["total_phase3_payoff"]

                    player.is_gpt_finished = True

                    if p_id in _thread_storage:
                        del _thread_storage[p_id]
                    return {player.id_in_group: {"status": "finished"}}
          
            return {player.id_in_group: {"status": "processing"}}
    
class Results(Page):
    @staticmethod
    def is_displayed(player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player):
        reason_history = player.participant.vars.get("reason_history", [])
        reason_history_2 = player.participant.vars.get("reason_history_2", [])
        total_phase2_payoff = player.participant.vars.get("total_phase2_payoff")
        total_phase3_payoff = player.participant.vars.get("total_phase3_payoff")

        return {
            "reason_history": reason_history,
            "reason_history_2": reason_history_2,
            "total_phase2_payoff": total_phase2_payoff,
            "total_phase3_payoff": total_phase3_payoff
        }

class ResultsWaitPage(WaitPage):
    title_text = "請等待其他受試者確認結果"

    wait_for_all_groups = True


page_sequence = [
    InstructionPage,
    ProcessingPage,
    Results,
    ResultsWaitPage
    ]

 